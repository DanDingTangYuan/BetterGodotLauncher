# Godot Auto Launcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview
Godot Auto Launcher is a lightweight, portable launcher and version manager for the Godot Engine. It automatically fetches the latest stable release from GitHub, downloads it, and allows you to easily switch between the Standard Edition and the C# (Mono) Edition without the hassle of manual file management.

## Features
* Smart Auto-Update: Automatically checks the GitHub API for the latest Godot releases.
* Dual Version Management: Keeps your Standard and Mono versions neatly separated.
* Portable Design: No installation required. All engine files are stored directly next to the executable in an engines/ folder.
* Bilingual Interface: Supports English and Traditional Chinese (zh_TW), remembering your preference.
* Background Downloading: Downloads and extracts engines silently without freezing the UI.

## Folder Structure
When you run the executable, it will automatically create the following structure:

Your_Folder/
├── GodotLauncher.exe
├── launcher_config.json
└── engines/
    ├── standard/
    └── mono/

## How to Use
1. Download the GodotLauncher.exe and place it in your preferred folder.
2. Run the executable.
3. The launcher will automatically check for the latest version. If the engines/ folders are empty, it will prompt to download the latest engines.
4. Click Launch Standard or Launch C# (Mono) to start creating your games!
