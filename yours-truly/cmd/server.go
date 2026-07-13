package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ChristianSch/hiro/yours-truly/adapters/search"
	appconfig "github.com/ChristianSch/hiro/yours-truly/config"
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
	cfg, err := appconfig.Load()
	if err != nil {
		panic(err)
	}

	logger := logging.InitLogger(cfg.Debug)
	defer logger.Sync()
	undo := zap.ReplaceGlobals(logger)
	defer undo()

	searcher, err := search.NewGrpcSearcher(search.GrpcSearcherConfig{
		Host:       cfg.Search.Address,
		Token:      cfg.Search.Token,
		Timeout:    cfg.Search.Timeout,
		Insecure:   cfg.Search.Insecure,
		ServerName: cfg.Search.ServerName,
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
		ReadTimeout:             cfg.HTTP.ReadTimeout,
		WriteTimeout:            cfg.HTTP.WriteTimeout,
		IdleTimeout:             cfg.HTTP.IdleTimeout,
		BodyLimit:               cfg.HTTP.BodyLimit,
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
		Max:        cfg.HTTP.SearchLimit,
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

	listenAddress := cfg.HTTP.Address
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
