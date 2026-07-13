package config

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/asaskevich/govalidator"
	"github.com/spf13/viper"
)

type HTTP struct {
	Address      string        `mapstructure:"address" valid:"required"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout" valid:"required"`
	WriteTimeout time.Duration `mapstructure:"write_timeout" valid:"required"`
	IdleTimeout  time.Duration `mapstructure:"idle_timeout" valid:"required"`
	BodyLimit    int           `mapstructure:"body_limit" valid:"required"`
	SearchLimit  int           `mapstructure:"search_rate_limit" valid:"required"`
}

type Search struct {
	Address    string        `mapstructure:"address" valid:"required"`
	Token      string        `mapstructure:"token" valid:"-"`
	Timeout    time.Duration `mapstructure:"timeout" valid:"required"`
	Insecure   bool          `mapstructure:"insecure" valid:"-"`
	ServerName string        `mapstructure:"server_name" valid:"-"`
}

type Config struct {
	Debug  bool   `mapstructure:"debug" valid:"-"`
	HTTP   HTTP   `mapstructure:"http" valid:"-"`
	Search Search `mapstructure:"search" valid:"-"`
}

func Load() (Config, error) {
	loader := viper.New()
	loader.SetConfigName("web")
	loader.SetConfigType("yaml")
	loader.AddConfigPath(".")
	loader.SetEnvPrefix("HIRO_WEB")
	loader.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	loader.AutomaticEnv()
	loader.SetTypeByDefaultValue(true)

	defaults := map[string]any{
		"debug":                  false,
		"http.address":           "127.0.0.1:8973",
		"http.read_timeout":      10 * time.Second,
		"http.write_timeout":     15 * time.Second,
		"http.idle_timeout":      60 * time.Second,
		"http.body_limit":        64 * 1024,
		"http.search_rate_limit": 60,
		"search.address":         "127.0.0.1:50053",
		"search.token":           "",
		"search.timeout":         5 * time.Second,
		"search.insecure":        true,
		"search.server_name":     "",
	}
	for key, value := range defaults {
		loader.SetDefault(key, value)
		if err := loader.BindEnv(key); err != nil {
			return Config{}, fmt.Errorf("bind %s: %w", key, err)
		}
	}

	if path := os.Getenv("HIRO_WEB_CONFIG"); path != "" {
		loader.SetConfigFile(path)
		if err := loader.ReadInConfig(); err != nil {
			return Config{}, fmt.Errorf("read web config: %w", err)
		}
	} else if err := loader.ReadInConfig(); err != nil {
		var notFound viper.ConfigFileNotFoundError
		if !errors.As(err, &notFound) {
			return Config{}, fmt.Errorf("read web config: %w", err)
		}
	}

	var cfg Config
	if err := loader.Unmarshal(&cfg); err != nil {
		return Config{}, fmt.Errorf("decode web config: %w", err)
	}
	if err := validate(cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func validate(cfg Config) error {
	if err := validateStruct("HTTP", cfg.HTTP); err != nil {
		return err
	}
	if err := validateStruct("search", cfg.Search); err != nil {
		return err
	}
	if cfg.HTTP.BodyLimit < 1 {
		return fmt.Errorf("http.body_limit must be at least 1")
	}
	if cfg.HTTP.SearchLimit < 1 {
		return fmt.Errorf("http.search_rate_limit must be at least 1")
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
