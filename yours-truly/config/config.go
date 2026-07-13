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
	Logging Logging `mapstructure:"logging" valid:"-"`
	HTTP    HTTP    `mapstructure:"http" valid:"-"`
	Search  Search  `mapstructure:"search" valid:"-"`
}

func Load(globalPath, servicePath string) (Config, error) {
	loader := viper.New()
	loader.SetConfigFile(globalPath)
	if err := loader.ReadInConfig(); err != nil {
		return Config{}, fmt.Errorf("read global config: %w", err)
	}

	loader.SetConfigFile(servicePath)
	if err := loader.MergeInConfig(); err != nil {
		return Config{}, fmt.Errorf("read web config: %w", err)
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
