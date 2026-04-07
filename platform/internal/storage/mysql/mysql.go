// Package mysql 提供 MySQL 连接初始化和自动建表能力。
package mysql

import (
	"database/sql"
	"log"
	"strconv"
	"time"

	mysqlDriver "github.com/go-sql-driver/mysql"

	"deeppool/platform/internal/config"
)

// NewDB 创建并返回 MySQL 连接池，自动 Ping 验证连通性。
func NewDB(cfg config.MySQLConfig) (*sql.DB, error) {
	log.Printf("[INFO] connecting mysql host=%s port=%d db=%s", cfg.Host, cfg.Port, cfg.Database)

	driverCfg := mysqlDriver.NewConfig()
	driverCfg.User = cfg.User
	driverCfg.Passwd = cfg.Password
	driverCfg.Net = "tcp"
	driverCfg.Addr = cfg.Host + ":" + strconv.Itoa(cfg.Port)
	driverCfg.DBName = cfg.Database
	driverCfg.ParseTime = true
	driverCfg.Params = map[string]string{
		"charset":   "utf8mb4",
		"collation": "utf8mb4_unicode_ci",
	}

	db, err := sql.Open("mysql", driverCfg.FormatDSN())
	if err != nil {
		return nil, err
	}

	db.SetMaxOpenConns(cfg.MaxOpenConns)
	db.SetMaxIdleConns(cfg.MaxIdleConns)
	db.SetConnMaxLifetime(time.Duration(cfg.ConnMaxLifetime) * time.Minute)

	if err = db.Ping(); err != nil {
		_ = db.Close()
		return nil, err
	}
	log.Printf("[INFO] mysql connected")

	return db, nil
}

// EnsureSchema 在指定的 db 上执行建表 DDL（幂等）。
func EnsureSchema(db *sql.DB, ddlStatements []string) error {
	for _, ddl := range ddlStatements {
		if _, err := db.Exec(ddl); err != nil {
			return err
		}
	}
	log.Printf("[INFO] schema ensured (%d statements)", len(ddlStatements))
	return nil
}

// AddColumnIfNotExists 幂等地为指定表添加列。
// MySQL 不支持 ALTER TABLE ADD COLUMN IF NOT EXISTS 语法，
// 因此通过 information_schema 查询列是否已存在来实现幂等。
func AddColumnIfNotExists(db *sql.DB, database, table, column, columnDef string) error {
	var count int
	err := db.QueryRow(
		"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? AND COLUMN_NAME = ?",
		database, table, column,
	).Scan(&count)
	if err != nil {
		return err
	}
	if count > 0 {
		log.Printf("[INFO] column %s.%s already exists, skip", table, column)
		return nil
	}
	alterSQL := "ALTER TABLE " + table + " ADD COLUMN " + columnDef
	if _, err := db.Exec(alterSQL); err != nil {
		return err
	}
	log.Printf("[INFO] column %s.%s added", table, column)
	return nil
}

// MigrateUniqueKey 幂等地重建 UNIQUE KEY：先 DROP 旧索引，再 CREATE 新索引。
// 如果 DROP 失败（索引不存在）则忽略，确保幂等。
func MigrateUniqueKey(db *sql.DB, table, keyName, columns string) {
	// 尝试 DROP 旧索引（不存在时忽略错误）
	_, _ = db.Exec("ALTER TABLE " + table + " DROP INDEX " + keyName)

	// 创建新索引
	alterSQL := "ALTER TABLE " + table + " ADD UNIQUE KEY " + keyName + " " + columns
	if _, err := db.Exec(alterSQL); err != nil {
		// 索引已存在（可能是新建的表）则忽略
		log.Printf("[WARNING] migrate unique key %s.%s: %v (may already exist)", table, keyName, err)
		return
	}
	log.Printf("[INFO] unique key %s.%s recreated with columns %s", table, keyName, columns)
}
