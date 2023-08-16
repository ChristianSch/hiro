package main

import (
	"fmt"

	"github.com/ChristianSch/hiro/yours-truly/adapters/search"
	"github.com/ChristianSch/hiro/yours-truly/infra/logging"
	"github.com/gofiber/contrib/fiberzap"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/template/html/v2"
	"go.uber.org/zap"
)

func main() {
	// build domain stuff
	searcher := search.NewSolrSearcher(search.SolarSearcherConfig{
		Core: "hproto",
		Host: "http://localhost:8983",
	})
	engine := html.New("./views", ".gohtml")
	app := fiber.New(fiber.Config{
		Views:                   engine,
		ViewsLayout:             "layouts/main",
		EnableTrustedProxyCheck: true,
	})

	// init logger with debug=false
	logger := logging.InitLogger(true) // conf.App.Debug)

	// for now we'll use zap as a global logger, not per dependency injection
	undo := zap.ReplaceGlobals(logger)
	defer undo()

	app.Use(fiberzap.New(fiberzap.Config{
		Logger: logger,
	}))

	app.Static("/static", "./static")
	app.Get("/", func(ctx *fiber.Ctx) error {
		return ctx.Render("search", fiber.Map{}, "layouts/main")
	})

	htmx := app.Group("/htmx")
	htmx.Get("/search", func(ctx *fiber.Ctx) error {
		query := ctx.Query("q")
		logger.Info("search", zap.String("query", query))

		res, err := searcher.Search(query)
		if err != nil {
			return err
		}

		ctx.Set("Hx-Push", fmt.Sprintf("%s/search?q=%s", ctx.BaseURL(), query))

		return ctx.Render("search", fiber.Map{
			"results": res,
			"query":   query,
		}, "layouts/empty")
	})

	if err := app.Listen(fmt.Sprintf(":%d", 8973)); err != nil {
		panic(err)
	}
}
