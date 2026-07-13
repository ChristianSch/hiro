package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/ChristianSch/hiro/yours-truly/adapters/search"
	"github.com/ChristianSch/hiro/yours-truly/infra/logging"
	"github.com/gofiber/contrib/fiberzap"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/limiter"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/gofiber/template/html/v2"
	"go.uber.org/zap"
)

const maxQueryBytes = 512

func main() {
	logger := logging.InitLogger(boolEnv("HIRO_DEBUG", false))
	defer logger.Sync()
	undo := zap.ReplaceGlobals(logger)
	defer undo()

	searcher, err := search.NewGrpcSearcher(search.GrpcSearcherConfig{
		Host:       envOrDefault("HIRO_SEARCH_GRPC_ADDRESS", "127.0.0.1:50053"),
		Token:      os.Getenv("HIRO_SERVICE_TOKEN"),
		Timeout:    durationEnv("HIRO_REQUEST_TIMEOUT", 5*time.Second),
		Insecure:   boolEnv("HIRO_GRPC_INSECURE", true),
		ServerName: os.Getenv("HIRO_GRPC_SERVER_NAME"),
	})
	if err != nil {
		logger.Fatal("initialize search client", zap.Error(err))
	}
	defer searcher.Close()

	engine := html.New("./views", ".gohtml")
	app := fiber.New(fiber.Config{
		Views:                   engine,
		ViewsLayout:             "layouts/main",
		EnableTrustedProxyCheck: true,
		ReadTimeout:             durationEnv("HIRO_HTTP_READ_TIMEOUT", 10*time.Second),
		WriteTimeout:            durationEnv("HIRO_HTTP_WRITE_TIMEOUT", 15*time.Second),
		IdleTimeout:             durationEnv("HIRO_HTTP_IDLE_TIMEOUT", 60*time.Second),
		BodyLimit:               intEnv("HIRO_HTTP_BODY_LIMIT", 64*1024),
		ErrorHandler: func(ctx *fiber.Ctx, handlerErr error) error {
			status := fiber.StatusInternalServerError
			var fiberErr *fiber.Error
			if errors.As(handlerErr, &fiberErr) {
				status = fiberErr.Code
			}
			if status >= fiber.StatusInternalServerError {
				logger.Error("request failed", zap.Error(handlerErr), zap.String("path", ctx.Path()))
			}
			return ctx.Status(status).SendString(http.StatusText(status))
		},
	})

	app.Use(recover.New())
	app.Use(func(ctx *fiber.Ctx) error {
		ctx.Set(fiber.HeaderXContentTypeOptions, "nosniff")
		ctx.Set(fiber.HeaderXFrameOptions, "DENY")
		ctx.Set(fiber.HeaderReferrerPolicy, "strict-origin-when-cross-origin")
		ctx.Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		return ctx.Next()
	})
	app.Use(fiberzap.New(fiberzap.Config{Logger: logger}))

	searchLimiter := limiter.New(limiter.Config{
		Max:        intEnv("HIRO_SEARCH_RATE_LIMIT", 60),
		Expiration: time.Minute,
		LimitReached: func(ctx *fiber.Ctx) error {
			return fiber.NewError(fiber.StatusTooManyRequests, "search rate limit exceeded")
		},
	})

	app.Static("/static", "./static", fiber.Static{MaxAge: 86400})
	app.Get("/", func(ctx *fiber.Ctx) error {
		return ctx.Render("search", fiber.Map{}, "layouts/main")
	})

	runSearch := func(layout string, pushHistory bool) fiber.Handler {
		return func(ctx *fiber.Ctx) error {
			query := ctx.Query("q")
			if len([]byte(query)) > maxQueryBytes {
				return fiber.NewError(fiber.StatusBadRequest, "query is too long")
			}
			results, err := searcher.Search(context.Background(), query)
			if err != nil {
				return fmt.Errorf("search backend: %w", err)
			}
			if pushHistory {
				ctx.Set("Hx-Push", "/search?q="+url.QueryEscape(query))
			}
			return ctx.Render("search", fiber.Map{
				"results": results,
				"query":   query,
			}, layout)
		}
	}

	htmx := app.Group("/htmx")
	htmx.Get("/status", func(ctx *fiber.Ctx) error {
		statusCtx, cancel := context.WithTimeout(context.Background(), 1500*time.Millisecond)
		defer cancel()
		status, err := searcher.Status(statusCtx)
		operational := err == nil && status.Operational
		if err != nil {
			logger.Warn("search status check failed", zap.Error(err))
		}
		ctx.Set(fiber.HeaderCacheControl, "no-store")
		return ctx.Render("status", fiber.Map{"operational": operational}, "layouts/empty")
	})
	htmx.Get("/random", searchLimiter, func(ctx *fiber.Ctx) error {
		results, err := searcher.Search(context.Background(), "")
		if err != nil {
			return fmt.Errorf("load recent websites: %w", err)
		}
		return ctx.Render("results", fiber.Map{"results": results}, "layouts/empty")
	})
	htmx.Get("/search", searchLimiter, runSearch("layouts/empty", true))
	app.Get("/search", searchLimiter, runSearch("layouts/main", false))

	listenAddress := envOrDefault("HIRO_HTTP_ADDRESS", "127.0.0.1:8973")
	serverErr := make(chan error, 1)
	go func() {
		serverErr <- app.Listen(listenAddress)
	}()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	defer signal.Stop(signals)

	select {
	case err := <-serverErr:
		if err != nil {
			logger.Fatal("HTTP server stopped", zap.Error(err))
		}
	case sig := <-signals:
		logger.Info("shutting down HTTP server", zap.String("signal", sig.String()))
		if err := app.ShutdownWithTimeout(10 * time.Second); err != nil {
			logger.Error("graceful shutdown failed", zap.Error(err))
		}
	}
}

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func boolEnv(name string, fallback bool) bool {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseBool(raw)
	if err != nil {
		panic(fmt.Errorf("invalid %s: %w", name, err))
	}
	return value
}

func intEnv(name string, fallback int) int {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value <= 0 {
		panic(fmt.Errorf("invalid %s integer %q", name, raw))
	}
	return value
}

func durationEnv(name string, fallback time.Duration) time.Duration {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := time.ParseDuration(raw)
	if err != nil || value <= 0 {
		panic(fmt.Errorf("invalid %s duration %q", name, raw))
	}
	return value
}
