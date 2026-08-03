# CHANGELOG

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

<!--

## Unreleased - YYYY-DD-mm

-->

## 1.0.0 - 2026-08-03

- Refactored the plugin to read/write structural geology data over the WebSDB REST API instead of
  a local PySDB `.sdb` SQLite file: connect with a server URL/username/password, then pick a
  project to work with.
- The plugin is now read/plot/import plus a bulk "Create/Update sites..." action against the connected project.
