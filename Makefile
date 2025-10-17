SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.ONESHELL:

CONFIG_FILE := packaging/macos/config.mk
-include $(CONFIG_FILE)

APP_NAME := SERP Companion
APP_BUNDLE_NAME := serpcompanion.app
APP_IDENTIFIER := com.serpcompanion.app
APP_VERSION ?= 0.1.1
EXTENSION_ID ?= kjeahghmchmcjnmhmbmlfcgkhjmkcpie

BUILD_DIR := build/macos
APP_BUNDLE := $(BUILD_DIR)/$(APP_BUNDLE_NAME)
PKGROOT := $(BUILD_DIR)/pkgroot
PKG_SCRIPTS := $(BUILD_DIR)/scripts
DIST_DIR := dist-installer
PKG_NAME := serpcompanion.pkg
PKG_PATH := $(DIST_DIR)/$(PKG_NAME)
LAUNCH_AGENT_LABEL := com.serp.companion.pairserver
LAUNCH_AGENT_DEST := /Library/LaunchAgents/$(LAUNCH_AGENT_LABEL).plist

.PHONY: macos-installer macos-release clean-macos pyinstaller-binaries

macos-installer: $(PKG_PATH)
	@printf "[macOS] Installer ready: %s\n" "$(PKG_PATH)"

macos-release: $(PKG_PATH)
	@printf "[macOS] PKG at %s\n" "$(PKG_PATH)"

$(PKG_PATH): $(PKGROOT) $(PKG_SCRIPTS)/postinstall | $(DIST_DIR)
	@command -v pkgbuild >/dev/null || { echo "pkgbuild not found. Install Xcode command line tools."; exit 1; }
	pkgbuild \
		--root "$(PKGROOT)" \
		--identifier "$(APP_IDENTIFIER)" \
		--version "$(APP_VERSION)" \
		--install-location "/Applications" \
		--scripts "$(PKG_SCRIPTS)" \
		"$(PKG_PATH)"

$(DIST_DIR):
	mkdir -p "$(DIST_DIR)"

$(PKGROOT): $(APP_BUNDLE)
	rm -rf "$(PKGROOT)"
	mkdir -p "$(PKGROOT)"
	ditto "$(APP_BUNDLE)" "$(PKGROOT)/$(APP_BUNDLE_NAME)"

$(PKG_SCRIPTS):
	mkdir -p "$(PKG_SCRIPTS)"

$(PKG_SCRIPTS)/postinstall: $(PKG_SCRIPTS) | $(APP_BUNDLE)
	@if [[ -z "$(EXTENSION_ID)" ]]; then \
		echo "EXTENSION_ID is empty. Provide one via EXTENSION_ID=your_id make macos-installer"; \
		exit 1; \
	fi
	python3 packaging/macos/write_postinstall.py \
		"$(PKG_SCRIPTS)/postinstall" \
		"$(EXTENSION_ID)" \
		"$(APP_BUNDLE_NAME)" \
		"$(LAUNCH_AGENT_DEST)" \
		"$(LAUNCH_AGENT_LABEL)"

pyinstaller-binaries:
	bash packaging/macos/build.sh

$(APP_BUNDLE): pyinstaller-binaries
	rm -rf "$(APP_BUNDLE)"
	mkdir -p "$(APP_BUNDLE)/Contents/MacOS"
	mkdir -p "$(APP_BUNDLE)/Contents/Resources/tools"
	cp "bin/serp-companion" "$(APP_BUNDLE)/Contents/MacOS/serp-companion"
	cp "bin/udemy-downloader" "$(APP_BUNDLE)/Contents/MacOS/udemy-downloader"
	chmod +x "$(APP_BUNDLE)/Contents/MacOS/serp-companion" "$(APP_BUNDLE)/Contents/MacOS/udemy-downloader"
	if [[ -d "tools" ]]; then \
		rm -rf "$(APP_BUNDLE)/Contents/Resources/tools"; \
		ditto "tools" "$(APP_BUNDLE)/Contents/Resources/tools"; \
		find "$(APP_BUNDLE)/Contents/Resources/tools" -type f -exec chmod +x {} \; 2>/dev/null || true; \
	fi
	if [[ -f "keyfile.json" ]]; then \
		cp "keyfile.json" "$(APP_BUNDLE)/Contents/Resources/keyfile.json"; \
	fi
	python3 packaging/macos/write_bundle_metadata.py \
		--bundle "$(APP_BUNDLE)" \
		--identifier "$(APP_IDENTIFIER)" \
		--name "$(APP_NAME)" \
		--version "$(APP_VERSION)" \
		--bundle-name "$(APP_BUNDLE_NAME)" \
		--launch-agent-label "$(LAUNCH_AGENT_LABEL)"

clean-macos:
	rm -rf "$(BUILD_DIR)" "$(DIST_DIR)/$(PKG_NAME)"
