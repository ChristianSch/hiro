package config

import (
	"fmt"
	"time"

	"github.com/asaskevich/govalidator"
	"github.com/spf13/viper"
)

type Logging struct {
	Debug bool `mapstructure:"debug" valid:"-"`
}

type Embedding struct {
	Address    string        `mapstructure:"address" valid:"required"`
	Token      string        `mapstructure:"token" valid:"-"`
	Timeout    time.Duration `mapstructure:"timeout" valid:"required"`
	Insecure   bool          `mapstructure:"insecure" valid:"-"`
	ServerName string        `mapstructure:"server_name" valid:"-"`
}

type Crawl struct {
	StartURL       string        `mapstructure:"start_url" valid:"-"`
	MaxDepth       int           `mapstructure:"max_depth" valid:"required"`
	MaxBodyBytes   int           `mapstructure:"max_body_bytes" valid:"required"`
	RequestTimeout time.Duration `mapstructure:"request_timeout" valid:"required"`
}

type Config struct {
	Logging   Logging   `mapstructure:"logging" valid:"-"`
	Embedding Embedding `mapstructure:"embedding" valid:"-"`
	Crawl     Crawl     `mapstructure:"crawl" valid:"-"`
}

func Load(globalPath, servicePath string) (Config, error) {
	loader := viper.New()
	loader.SetConfigFile(globalPath)
	if err := loader.ReadInConfig(); err != nil {
		return Config{}, fmt.Errorf("read global config: %w", err)
	}

	loader.SetConfigFile(servicePath)
	if err := loader.MergeInConfig(); err != nil {
		return Config{}, fmt.Errorf("read crawler config: %w", err)
	}

	var cfg Config
	if err := loader.Unmarshal(&cfg); err != nil {
		return Config{}, fmt.Errorf("decode crawler config: %w", err)
	}
	if err := validate(cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func validate(cfg Config) error {
	if err := validateStruct("embedding", cfg.Embedding); err != nil {
		return err
	}
	if err := validateStruct("crawl", cfg.Crawl); err != nil {
		return err
	}
	if cfg.Crawl.MaxDepth < 1 {
		return fmt.Errorf("crawl.max_depth must be at least 1")
	}
	if cfg.Crawl.MaxBodyBytes < 1 {
		return fmt.Errorf("crawl.max_body_bytes must be at least 1")
	}
	return nil
}

func validateStruct(name string, value any) error {
	ok, err := govalidator.ValidateStruct(value)
	if err != nil {
		return fmt.Errorf("invalid %s config: %w", name, err)
	}
	if !ok {
		return fmt.Errorf("invalid %s config", name)
	}
	return nil
}
