package crawl

import (
	"bytes"
	"context"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"
	"github.com/ChristianSch/hiro/protagonist/domain/model/index"
	"github.com/gocolly/colly/v2"
	"go.uber.org/zap"

	"github.com/PuerkitoBio/goquery"
)

const defaultMaxBodySize = 2 * 1024 * 1024

type CollyConfig struct {
	Indexer        index.PageIndexer
	MaxDepth       *int
	MaxBodySize    int
	RequestTimeout time.Duration
	AllowPrivate   bool
}

type CollyCrawler struct {
	c       *colly.Collector
	cfg     CollyConfig
	indexer index.PageIndexer
}

func NewCollyCrawler(cfg CollyConfig) *CollyCrawler {
	maxDepth := 2
	if cfg.MaxDepth != nil {
		maxDepth = *cfg.MaxDepth
	}
	if maxDepth < 1 {
		maxDepth = 1
	}
	if cfg.MaxBodySize <= 0 {
		cfg.MaxBodySize = defaultMaxBodySize
	}
	if cfg.RequestTimeout <= 0 {
		cfg.RequestTimeout = 15 * time.Second
	}

	collector := colly.NewCollector(
		colly.MaxDepth(maxDepth),
		colly.Async(true),
		colly.MaxBodySize(cfg.MaxBodySize),
	)
	collector.SetRequestTimeout(cfg.RequestTimeout)
	collector.Limit(&colly.LimitRule{
		DomainGlob:  "*",
		Delay:       250 * time.Millisecond,
		RandomDelay: 750 * time.Millisecond,
		Parallelism: 2,
	})
	collector.WithTransport(safeTransport(cfg.AllowPrivate))

	return &CollyCrawler{c: collector, cfg: cfg, indexer: cfg.Indexer}
}

func safeTransport(allowPrivate bool) *http.Transport {
	dialer := &net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}
	return &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		ForceAttemptHTTP2:     true,
		MaxIdleConns:          20,
		MaxIdleConnsPerHost:   4,
		IdleConnTimeout:       60 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ResponseHeaderTimeout: 10 * time.Second,
		DialContext: func(ctx context.Context, network, address string) (net.Conn, error) {
			host, port, err := net.SplitHostPort(address)
			if err != nil {
				return nil, fmt.Errorf("invalid target address: %w", err)
			}
			addresses, err := net.DefaultResolver.LookupIPAddr(ctx, host)
			if err != nil {
				return nil, fmt.Errorf("resolve target host: %w", err)
			}
			for _, resolved := range addresses {
				if !allowPrivate && unsafeIP(resolved.IP) {
					return nil, fmt.Errorf("target resolves to a private or non-routable address")
				}
			}
			if len(addresses) == 0 {
				return nil, fmt.Errorf("target host has no addresses")
			}
			return dialer.DialContext(ctx, network, net.JoinHostPort(addresses[0].IP.String(), port))
		},
	}
}

func unsafeIP(ip net.IP) bool {
	return ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() ||
		ip.IsLinkLocalMulticast() || ip.IsUnspecified() || ip.IsMulticast()
}

func normalizeURL(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	u.Fragment = ""
	u.Scheme = strings.ToLower(u.Scheme)
	u.Host = strings.ToLower(u.Host)
	if u.Path != "/" {
		u.Path = strings.TrimRight(u.Path, "/")
	}
	return u.String()
}

func (c *CollyCrawler) Crawl(startingPoint string) error {
	startURL, err := url.ParseRequestURI(startingPoint)
	if err != nil || (startURL.Scheme != "http" && startURL.Scheme != "https") || startURL.Hostname() == "" {
		return fmt.Errorf("starting URL must be an absolute HTTP or HTTPS URL")
	}
	if c.indexer == nil {
		return fmt.Errorf("page indexer is required")
	}
	c.c.AllowedDomains = []string{startURL.Hostname()}

	var errorMu sync.Mutex
	var firstErr error
	recordError := func(err error) {
		if err == nil {
			return
		}
		errorMu.Lock()
		defer errorMu.Unlock()
		if firstErr == nil {
			firstErr = err
		}
	}

	c.c.OnHTML("a[href]", func(element *colly.HTMLElement) {
		href := strings.TrimSpace(element.Attr("href"))
		if href == "" {
			return
		}
		if err := element.Request.Visit(href); err != nil && err != colly.ErrAlreadyVisited {
			zap.L().Debug("skipping discovered URL", zap.Error(err))
		}
	})

	c.c.OnResponse(func(response *colly.Response) {
		contentType := strings.ToLower(response.Headers.Get("Content-Type"))
		if !strings.HasPrefix(contentType, "text/html") && !strings.HasPrefix(contentType, "application/xhtml+xml") {
			zap.L().Debug("skipping non-HTML response", zap.String("content_type", contentType))
			return
		}

		pageURL := normalizeURL(response.Request.URL.String())
		document, parseErr := goquery.NewDocumentFromReader(bytes.NewReader(response.Body))
		if parseErr != nil {
			recordError(fmt.Errorf("parse %s: %w", pageURL, parseErr))
			return
		}

		references := make([]crawl.CrawlReference, 0)
		document.Find("a[href]").Each(func(_ int, selection *goquery.Selection) {
			if link, ok := selection.Attr("href"); ok {
				references = append(references, link)
			}
		})

		result := crawl.CrawlResult{
			Url:         pageURL,
			Title:       strings.TrimSpace(document.Find("title").First().Text()),
			Description: strings.TrimSpace(document.Find(`meta[name="description"]`).First().AttrOr("content", "")),
			Body:        strings.Join(strings.Fields(document.Find("body").Text()), " "),
			References:  references,
		}
		if result.Body == "" {
			return
		}
		if err := c.indexer.PutPage(result); err != nil {
			recordError(fmt.Errorf("index %s: %w", pageURL, err))
			return
		}
		zap.L().Info("indexed page", zap.String("url", pageURL), zap.Int("references", len(references)))
	})

	c.c.OnError(func(response *colly.Response, requestErr error) {
		pageURL := startingPoint
		if response != nil && response.Request != nil && response.Request.URL != nil {
			pageURL = response.Request.URL.String()
		}
		recordError(fmt.Errorf("crawl %s: %w", pageURL, requestErr))
	})

	if err := c.c.Visit(startingPoint); err != nil {
		return err
	}
	c.c.Wait()

	errorMu.Lock()
	defer errorMu.Unlock()
	return firstErr
}
