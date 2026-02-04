#!/usr/bin/env python3
"""
GAS Dashboard Server v3 - Combined with Swarm Dashboard v6 Quality
===================================================================
Self-contained dashboard server combining:
- v6's Capybara-inspired color palette and design
- v6's FilePositionTracker and BoundedParseCache for performance
- GAS-specific features: waves, generations, succession events, knowledge store
- Light/dark theme toggle
- Clickable agent detail panels
- Live activity feed
"""

import os
import sys
import json
import signal
import logging
import glob
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any, Tuple

# =============================================================================
# Configuration
# =============================================================================

GAS_DIR = os.getenv('GAS_DIR', '/workspace/project-gas')
GAS_NAME = os.getenv('GAS_NAME', 'GAS Task')
GAS_MODE = os.getenv('GAS_MODE', 'swarm')
PORT = int(os.getenv('GAS_PORT', '8080'))

IDLE_THRESHOLD_SECONDS = 60
COMPLETION_THRESHOLD_SECONDS = 120
MAX_CACHE_SIZE = 50
MAX_LIVE_EVENTS = 30
MAX_CONTENT_LENGTH = 200
MAX_FILES_CREATED = 20

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

SERVER_START_TIME = datetime.utcnow().isoformat() + 'Z'

COMPLETION_MARKERS = [
    'EVOLUTION COMPLETE',
    'Task completed',
    'All tasks completed',
    'status": "completed"',
    'Successfully completed',
    'Finished all',
    'COMPLETED',
    'Done!',
]


# =============================================================================
# Embedded Dashboard HTML (Capybara-inspired design from swarm-dashboard v6)
# =============================================================================

DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GAS Dashboard v3</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Courier+Prime:wght@400;700&display=swap" rel="stylesheet">
  <style>
/* ==============================================
   GAS Dashboard CSS - Extracted from Swarm Dashboard v6
   with Capybara-Inspired Color Palette
   ============================================== */

/* ==============================================
   DESIGN TOKENS - CSS Custom Properties
   ============================================== */
:root {
  /* Colors - Background */
  --color-bg-primary: #F9F6F1;
  --color-bg-secondary: #F0EEE7;
  --color-bg-card: #FFFFFF;
  --color-bg-overlay: rgba(0, 0, 0, 0.5);

  /* Colors - Text */
  --color-text-primary: #111827;
  --color-text-secondary: #6b7280;
  --color-text-muted: #9ca3af;
  --color-text-inverse: #ffffff;

  /* Colors - Border */
  --color-border: #e5e7eb;
  --color-border-muted: #d1d5db;
  --color-border-focus: #FF6B4A;

  /* Colors - Accent (Coral) */
  --color-coral: #FF6B4A;
  --color-coral-light: #FF7A5C;
  --color-coral-hover: #e55a3a;
  --color-coral-bg: rgba(255, 107, 74, 0.1);

  /* Colors - Status (Capybara-Inspired Natural Palette) */
  --color-success: #7D9B76;
  --color-success-bg: rgba(125, 155, 118, 0.12);
  --color-warning: #D4A76A;
  --color-warning-bg: rgba(212, 167, 106, 0.12);
  --color-error: #C67A6B;
  --color-error-bg: rgba(198, 122, 107, 0.12);
  --color-status-running: #FF6B4A;
  --color-status-idle: #7BA3A8;
  --color-status-pending: #9B8B7A;
  --color-status-complete: #7D9B76;

  /* Typography */
  --font-heading: 'Instrument Serif', Georgia, serif;
  --font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
  --font-mono: 'Courier Prime', 'SF Mono', Monaco, 'Courier New', monospace;

  /* Font Sizes */
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-size-2xl: 1.5rem;
  --font-size-3xl: 1.875rem;
  --font-size-4xl: 2.25rem;

  /* Spacing */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-10: 2.5rem;
  --space-12: 3rem;

  /* Border Radius */
  --radius-sm: 0.125rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-xl: 0.75rem;
  --radius-2xl: 1rem;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1);
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.03);
  --shadow-card-hover: 0 8px 24px rgba(0, 0, 0, 0.1);

  /* Gradients */
  --gradient-coral: linear-gradient(135deg, #FF6B4A 0%, #FF8A6B 100%);
  --gradient-success: linear-gradient(135deg, #7D9B76 0%, #8FAD82 50%, #9AAD7A 100%);
  --gradient-idle: linear-gradient(135deg, #7BA3A8 0%, #8EB3B8 100%);
  --gradient-warm-bg: linear-gradient(180deg, #F9F6F1 0%, #F0EEE7 100%);

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-default: 200ms ease;
  --transition-slow: 300ms ease;
}

/* Dark Mode */
[data-theme="dark"] {
  --color-bg-primary: #121212;
  --color-bg-secondary: #1a1a1a;
  --color-bg-card: #2a2a2a;
  --color-bg-overlay: rgba(0, 0, 0, 0.7);
  --color-text-primary: #ffffff;
  --color-text-secondary: #9ca3af;
  --color-text-muted: #6b7280;
  --color-text-inverse: #111827;
  --color-border: #374151;
  --color-border-muted: #4b5563;
  --color-coral-bg: rgba(255, 107, 74, 0.15);
  --color-success-bg: rgba(125, 155, 118, 0.15);
  --color-warning-bg: rgba(212, 167, 106, 0.15);
  --color-error-bg: rgba(198, 122, 107, 0.15);
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.1);
  --shadow-card-hover: 0 8px 24px rgba(0, 0, 0, 0.3);
  --gradient-warm-bg: linear-gradient(180deg, #121212 0%, #1a1a1a 100%);
}

/* ==============================================
   BASE STYLES - Reset & Typography
   ============================================== */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  min-height: 100vh;
}

body {
  font-family: var(--font-body);
  font-size: var(--font-size-base);
  line-height: 1.5;
  color: var(--color-text-primary);
  background: var(--gradient-warm-bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

h1, h2, h3, h4 {
  font-family: var(--font-heading);
  font-weight: 400;
  line-height: 1.25;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
}

::-webkit-scrollbar-thumb {
  background: var(--color-border-muted);
  border-radius: var(--radius-full);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--color-coral);
}

/* ==============================================
   LAYOUT STYLES
   ============================================== */
.app {
  display: flex;
  min-height: 100vh;
  width: 100%;
  position: relative;
  overflow: hidden;
}

.main-panel {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  transition: margin-right var(--transition-slow);
}

.app.detail-open .main-panel {
  margin-right: 480px;
}

.container {
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ==============================================
   HEADER STYLES
   ============================================== */
.dashboard-header {
  padding: var(--space-6) 0;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.header-top {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.header-title-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.header-title-wrapper {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.pulse-indicator {
  width: 12px;
  height: 12px;
  border-radius: var(--radius-full);
  background: var(--color-status-running);
  position: relative;
  flex-shrink: 0;
}

.pulse-indicator::before {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: var(--radius-full);
  background: var(--color-status-running);
  opacity: 0;
  animation: pulse-ring 2s ease-out infinite;
}

.pulse-indicator.completed {
  background: var(--color-success);
}

.pulse-indicator.completed::before {
  animation: none;
}

@keyframes pulse-ring {
  0% { transform: scale(1); opacity: 0.4; }
  100% { transform: scale(2); opacity: 0; }
}

.dashboard-title {
  font-size: var(--font-size-4xl);
  color: var(--color-text-primary);
}

.swarm-name {
  font-family: var(--font-heading);
  font-size: var(--font-size-lg);
  font-weight: 400;
  color: var(--color-text-secondary);
}

.header-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-1);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.meta-value {
  font-family: var(--font-mono);
  color: var(--color-text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition-default);
}

.theme-toggle:hover {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
}

/* ==============================================
   STATS BAR STYLES
   ============================================== */
.stats-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-5);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
  min-width: 120px;
  transition: var(--transition-default);
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.stat-label {
  font-size: var(--font-size-xs);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted);
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  line-height: 1;
}

.stat-value.running { color: var(--color-status-running); }
.stat-value.completed { color: var(--color-success); }
.stat-value.failed { color: var(--color-error); }
.stat-value.pending { color: var(--color-status-pending); }
.stat-value.idle { color: var(--color-status-idle); }

/* ==============================================
   PROGRESS SECTION STYLES
   ============================================== */
.progress-section {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-2xl);
  padding: var(--space-5) var(--space-6);
  box-shadow: var(--shadow-card);
  margin-bottom: var(--space-6);
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.progress-title {
  font-family: var(--font-body);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.progress-percentage {
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--color-text-primary);
}

.progress-percentage.complete {
  color: var(--color-success);
}

.progress-bar-container {
  position: relative;
  width: 100%;
  height: 12px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-bar-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: var(--gradient-coral);
  border-radius: var(--radius-full);
  transition: width var(--transition-slow);
}

.progress-bar-fill.complete {
  background: var(--gradient-success);
}

.progress-bar-fill.active::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.3) 50%, transparent 100%);
  animation: progressShimmer 1.5s ease-in-out infinite;
}

@keyframes progressShimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* ==============================================
   AGENTS GRID STYLES
   ============================================== */
.agents-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  padding-bottom: var(--space-12);
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

/* ==============================================
   AGENT CARD STYLES
   ============================================== */
.agent-card {
  position: relative;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-2xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: transform var(--transition-default), box-shadow var(--transition-default);
  overflow: hidden;
}

.agent-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--color-border-muted);
  transition: background var(--transition-default);
}

.agent-card.running::before { background: var(--color-status-running); }
.agent-card.completed::before { background: var(--color-success); }
.agent-card.failed::before { background: var(--color-error); }
.agent-card.pending::before { background: var(--color-status-pending); }
.agent-card.idle::before { background: var(--color-status-idle); }

.agent-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}

.agent-card.selected {
  border-color: var(--color-coral);
  background: var(--color-bg-secondary);
}

.agent-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.agent-card__role {
  font-family: var(--font-heading);
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: var(--color-text-primary);
}

.agent-card__last-activity {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--space-3);
}

.agent-card__last-activity.stale {
  color: var(--color-warning);
}

.agent-card__progress {
  height: 6px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: var(--space-3);
}

.agent-card__progress-fill {
  height: 100%;
  background: var(--gradient-coral);
  border-radius: var(--radius-full);
  transition: width var(--transition-slow);
}

.agent-card__progress-fill.completed {
  background: var(--gradient-success);
}

.agent-card__progress-fill.idle {
  background: var(--gradient-idle);
}

.agent-card__meta {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.agent-card__tools {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--color-text-secondary);
}

/* ==============================================
   STATUS BADGE STYLES
   ============================================== */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-badge.running {
  background: var(--color-coral-bg);
  color: var(--color-status-running);
  animation: pulse 2s ease-in-out infinite;
}

.status-badge.completed {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.status-badge.failed {
  background: var(--color-error-bg);
  color: var(--color-error);
}

.status-badge.pending {
  background: rgba(155, 139, 122, 0.12);
  color: var(--color-status-pending);
}

.status-badge.idle {
  background: rgba(123, 163, 168, 0.12);
  color: var(--color-status-idle);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* ==============================================
   DETAIL PANEL STYLES
   ============================================== */
.detail-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 480px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-left: 1px solid var(--color-border);
  box-shadow: var(--shadow-xl);
  transform: translateX(100%);
  transition: transform var(--transition-slow);
  z-index: 300;
  overflow: hidden;
}

.detail-panel.open,
.app.detail-open .detail-panel {
  transform: translateX(0);
}

.detail-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.detail-panel-title h2 {
  font-family: var(--font-heading);
  font-size: var(--font-size-xl);
  color: var(--color-text-primary);
}

.detail-panel-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.detail-panel-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  border-radius: var(--radius-lg);
  transition: var(--transition-fast);
}

.detail-panel-close:hover {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
}

.detail-panel-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
}

.detail-section {
  margin-bottom: var(--space-6);
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border);
}

.detail-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.detail-info-item {
  background: var(--color-bg-secondary);
  padding: var(--space-3);
  border-radius: var(--radius-lg);
}

.detail-info-item.full-width {
  grid-column: 1 / -1;
}

.detail-info-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.detail-info-value {
  font-size: var(--font-size-base);
  font-weight: 500;
  color: var(--color-text-primary);
  margin-top: var(--space-1);
}

.detail-tools-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.tool-stat {
  background: var(--color-bg-secondary);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.tool-name {
  font-size: var(--font-size-sm);
}

.tool-count {
  font-size: var(--font-size-sm);
  color: var(--color-coral);
  font-weight: 600;
}

/* Activity Feed */
.activity-feed {
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  max-height: 400px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.activity-item {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
}

.activity-icon.tool {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.activity-icon.thinking {
  background: rgba(123, 163, 168, 0.2);
  color: #7BA3A8;
}

.activity-icon.result {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.activity-content {
  flex: 1;
  overflow: hidden;
  word-break: break-word;
}

.activity-tool {
  color: var(--color-coral);
  font-weight: 500;
}

.activity-text {
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

/* Files List */
.files-list {
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.file-item {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.file-item:last-child {
  border-bottom: none;
}

.file-icon {
  color: var(--color-text-muted);
}

/* Overlay */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  opacity: 0;
  visibility: hidden;
  transition: var(--transition-slow);
  z-index: 200;
}

.app.detail-open .overlay {
  opacity: 1;
  visibility: visible;
}

/* Connection Status */
.connection-status {
  position: fixed;
  bottom: var(--space-4);
  left: var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  box-shadow: var(--shadow-md);
  z-index: 100;
}

.connection-status.connected {
  border-color: var(--color-success);
}

.connection-status.disconnected {
  border-color: var(--color-error);
  color: var(--color-error);
}

.connection-status .status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}

.connection-status.connected .status-dot {
  background: var(--color-success);
  animation: pulse 2s ease-in-out infinite;
}

.connection-status.disconnected .status-dot {
  background: var(--color-error);
}

/* ==============================================
   RESPONSIVE STYLES
   ============================================== */
@media screen and (max-width: 1024px) {
  .container {
    padding: 0 var(--space-4);
  }

  .app.detail-open .main-panel {
    margin-right: 400px;
  }

  .detail-panel {
    width: 400px;
  }

  .agents-grid {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  }

  .dashboard-title {
    font-size: var(--font-size-3xl);
  }
}

@media screen and (max-width: 639px) {
  .container {
    padding: 0 var(--space-3);
  }

  .app.detail-open .main-panel {
    margin-right: 0;
  }

  .detail-panel {
    width: 100%;
    max-width: 100vw;
  }

  .header-top {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-meta {
    align-items: flex-start;
    flex-direction: row;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .dashboard-title {
    font-size: var(--font-size-2xl);
  }

  .stats-bar {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: var(--space-2);
    -webkit-overflow-scrolling: touch;
  }

  .stat-card {
    flex-shrink: 0;
    min-width: 110px;
  }

  .agents-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* Empty state */
.empty-state {
  text-align: center;
  padding: var(--space-12) var(--space-6);
  color: var(--color-text-muted);
}

/* ==============================================
   GAS-SPECIFIC STYLES
   ============================================== */

/* Generation Badges */
.gen-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 22px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  font-weight: 600;
  font-family: var(--font-mono);
}

.gen-badge.active {
  background: var(--color-coral-bg);
  color: var(--color-coral);
}

.gen-badge.completed {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.gen-badge.pending {
  background: rgba(155, 139, 122, 0.12);
  color: var(--color-status-pending);
}

/* Generation-specific colors for G1, G2, G3 */
.gen-badge.g1 {
  background: var(--color-coral-bg);
  color: var(--color-coral);
  border: 1px solid var(--color-coral);
}

.gen-badge.g2 {
  background: var(--color-success-bg);
  color: var(--color-success);
  border: 1px solid var(--color-success);
}

.gen-badge.g3 {
  background: rgba(123, 163, 168, 0.12);
  color: var(--color-status-idle);
  border: 1px solid var(--color-status-idle);
}

/* Succession Timeline */
.succession-timeline {
  position: relative;
  padding: var(--space-4) 0;
  margin: var(--space-4) 0;
}

.succession-timeline::before {
  content: '';
  position: absolute;
  left: 16px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--color-border);
}

.succession-event {
  position: relative;
  padding-left: var(--space-10);
  padding-bottom: var(--space-4);
  margin-bottom: var(--space-2);
}

.succession-event:last-child {
  padding-bottom: 0;
  margin-bottom: 0;
}

.succession-event::before {
  content: '';
  position: absolute;
  left: 10px;
  top: 4px;
  width: 14px;
  height: 14px;
  border-radius: var(--radius-full);
  background: var(--color-bg-card);
  border: 2px solid var(--color-border);
  z-index: 1;
}

.succession-event.active::before {
  background: var(--color-coral);
  border-color: var(--color-coral);
  animation: pulse-ring 2s ease-out infinite;
}

.succession-event.completed::before {
  background: var(--color-success);
  border-color: var(--color-success);
}

.succession-event.pending::before {
  background: var(--color-bg-secondary);
  border-color: var(--color-status-pending);
}

.succession-event__title {
  font-family: var(--font-heading);
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.succession-event__time {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--space-2);
}

.succession-event__description {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.succession-event__gen-badge {
  display: inline-block;
  margin-left: var(--space-2);
}

/* Knowledge Store Cards */
.knowledge-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  box-shadow: var(--shadow-card);
  transition: var(--transition-default);
}

.knowledge-card:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}

.knowledge-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.knowledge-card__title {
  font-family: var(--font-heading);
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.knowledge-card__icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-coral-bg);
  color: var(--color-coral);
  border-radius: var(--radius-lg);
}

.knowledge-card__description {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
  line-height: 1.5;
}

.knowledge-card__stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.knowledge-stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  min-width: 80px;
}

.knowledge-stat__label {
  font-size: var(--font-size-xs);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted);
}

.knowledge-stat__value {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
}

.knowledge-stat__value.highlight {
  color: var(--color-coral);
}

/* Knowledge Store Grid */
.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}

/* Wave Indicators with Generation Counts */
.wave-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
}

.wave-indicator__label {
  font-family: var(--font-heading);
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.wave-indicator__counts {
  display: flex;
  gap: var(--space-2);
}

.wave-indicator__count {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  font-weight: 600;
  font-family: var(--font-mono);
}

.wave-indicator__count.g1 {
  background: var(--color-coral-bg);
  color: var(--color-coral);
}

.wave-indicator__count.g2 {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.wave-indicator__count.g3 {
  background: rgba(123, 163, 168, 0.12);
  color: var(--color-status-idle);
}

.wave-indicator__count-number {
  font-weight: 700;
}

/* Wave Progress Bar with Generation Segments */
.wave-progress {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: var(--space-4) 0;
}

.wave-progress__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.wave-progress__title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.wave-progress__percentage {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.wave-progress__bar {
  position: relative;
  height: 10px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
  display: flex;
}

.wave-progress__segment {
  height: 100%;
  transition: width var(--transition-slow);
}

.wave-progress__segment.g1 {
  background: var(--color-coral);
}

.wave-progress__segment.g2 {
  background: var(--color-success);
}

.wave-progress__segment.g3 {
  background: var(--color-status-idle);
}

/* Generation Summary Card */
.generation-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin: var(--space-6) 0;
}

.generation-summary__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-4);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
  text-align: center;
}

.generation-summary__item.g1 {
  border-top: 3px solid var(--color-coral);
}

.generation-summary__item.g2 {
  border-top: 3px solid var(--color-success);
}

.generation-summary__item.g3 {
  border-top: 3px solid var(--color-status-idle);
}

.generation-summary__badge {
  margin-bottom: var(--space-2);
}

.generation-summary__count {
  font-size: var(--font-size-3xl);
  font-weight: 700;
  font-family: var(--font-mono);
  line-height: 1;
  margin-bottom: var(--space-1);
}

.generation-summary__item.g1 .generation-summary__count {
  color: var(--color-coral);
}

.generation-summary__item.g2 .generation-summary__count {
  color: var(--color-success);
}

.generation-summary__item.g3 .generation-summary__count {
  color: var(--color-status-idle);
}

.generation-summary__label {
  font-size: var(--font-size-xs);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted);
}

/* Responsive adjustments for GAS components */
@media screen and (max-width: 639px) {
  .knowledge-grid {
    grid-template-columns: 1fr;
  }

  .generation-summary {
    grid-template-columns: 1fr;
    gap: var(--space-3);
  }

  .wave-indicator {
    flex-direction: column;
    align-items: flex-start;
  }

  .succession-event {
    padding-left: var(--space-8);
  }

  .succession-timeline::before {
    left: 12px;
  }

  .succession-event::before {
    left: 6px;
    width: 12px;
    height: 12px;
  }
}
  </style>
</head>
<body class="no-theme-transition">
  <div class="app" id="app">
    <!-- Main Panel -->
    <div class="main-panel">
      <div class="container">
        <!-- Dashboard Header -->
        <header class="dashboard-header">
          <div class="header-content">
            <!-- Top Section: Title and Meta -->
            <div class="header-top">
              <div class="header-title-section">
                <div class="header-title-wrapper">
                  <div class="pulse-indicator" id="pulse-indicator"></div>
                  <h1 class="dashboard-title">GAS v3 Dashboard</h1>
                </div>
                <p class="swarm-name" id="project-name">Loading...</p>
                <p class="task-objective" id="task-objective"></p>
              </div>

              <div class="header-actions">
                <div class="header-meta">
                  <div class="meta-item">
                    <span class="meta-label">Mode:</span>
                    <span class="meta-value" id="gas-mode">swarm</span>
                  </div>
                  <div class="meta-item">
                    <span class="meta-label">Wave:</span>
                    <span class="meta-value" id="current-wave">1</span>
                  </div>
                  <div class="meta-item">
                    <span class="meta-label">Elapsed:</span>
                    <span class="meta-value" id="elapsed-time">--:--:--</span>
                  </div>
                  <div class="meta-item">
                    <span class="meta-label">Updated:</span>
                    <span class="meta-value" id="last-updated">Just now</span>
                  </div>
                </div>
                <button class="theme-toggle" id="theme-toggle" aria-label="Toggle theme">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                  </svg>
                </button>
              </div>
            </div>

            <!-- Stats Bar -->
            <div class="stats-bar" id="stats-bar">
              <div class="stat-card">
                <span class="stat-label">Agents</span>
                <span class="stat-value" id="total-agents">-</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Generations</span>
                <span class="stat-value" id="total-generations">-</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Patterns</span>
                <span class="stat-value" id="patterns-count">-</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Successions</span>
                <span class="stat-value" id="successions-count">-</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Running</span>
                <span class="stat-value running" id="running-count">-</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Completed</span>
                <span class="stat-value completed" id="completed-count">-</span>
              </div>
            </div>

            <!-- Overall Progress Section -->
            <section class="progress-section">
              <div class="progress-header">
                <h2 class="progress-title">Overall Progress</h2>
                <span class="progress-percentage" id="overall-percentage">0%</span>
              </div>
              <div class="progress-bar-container">
                <div class="progress-bar-fill active" id="overall-progress" style="width: 0%;"></div>
              </div>
            </section>
          </div>
        </header>

        <!-- Main Content: Waves and Agents -->
        <main class="agents-container">
          <!-- Waves will be dynamically generated here -->
          <div id="waves-container">
            <p class="empty-state">Loading agents...</p>
          </div>

          <!-- Knowledge Sidebar (inline for layout) -->
          <aside class="knowledge-sidebar" id="knowledge-sidebar">
            <div class="sidebar-section">
              <h3 class="sidebar-title">Accumulated Knowledge</h3>
              <div class="knowledge-grid">
                <div class="knowledge-card">
                  <span class="knowledge-value" id="success-patterns">0</span>
                  <span class="knowledge-label">Success Patterns</span>
                </div>
                <div class="knowledge-card">
                  <span class="knowledge-value" id="anti-patterns">0</span>
                  <span class="knowledge-label">Anti-Patterns</span>
                </div>
                <div class="knowledge-card">
                  <span class="knowledge-value" id="domain-insights">0</span>
                  <span class="knowledge-label">Domain Insights</span>
                </div>
              </div>
            </div>

            <div class="sidebar-section">
              <h3 class="sidebar-title">Succession Events</h3>
              <div class="succession-list" id="succession-list">
                <p class="empty-state-small">No successions yet</p>
              </div>
            </div>
          </aside>
        </main>
      </div>
    </div>

    <!-- Detail Panel (Sidebar) -->
    <aside class="detail-panel" id="detail-panel" aria-hidden="true">
      <div class="detail-panel-header">
        <div class="detail-panel-title">
          <h2 id="detail-title">Agent Details</h2>
          <p class="detail-panel-subtitle" id="detail-subtitle"></p>
        </div>
        <button class="detail-panel-close" aria-label="Close detail panel" onclick="closeDetailPanel()">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M15 5L5 15M5 5l10 10"/>
          </svg>
        </button>
      </div>

      <div class="detail-panel-content" id="detail-content">
        <!-- Populated by JavaScript -->
      </div>
    </aside>

    <!-- Overlay (for mobile) -->
    <div class="overlay" onclick="closeDetailPanel()"></div>
  </div>

  <!-- Connection Status Indicator -->
  <div class="connection-status" id="connection-status">
    <span class="status-dot"></span>
    <span id="connection-text">Connecting...</span>
  </div>
</body>
  <script>
// =============================================================================
// GAS v3 Dashboard JavaScript
// =============================================================================

// Dashboard State
let gasData = null;
let selectedAgent = null;
let connectionOk = false;

// =============================================================================
// Theme Toggle
// =============================================================================

const themeToggle = document.getElementById('theme-toggle');
const html = document.documentElement;

function initTheme() {
  const savedTheme = localStorage.getItem('gas-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = savedTheme || (prefersDark ? 'dark' : 'light');
  html.setAttribute('data-theme', theme);
  updateThemeIcon(theme);
}

function updateThemeIcon(theme) {
  const icon = themeToggle.querySelector('svg');
  if (theme === 'dark') {
    icon.innerHTML = `
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
    `;
  } else {
    icon.innerHTML = `
      <circle cx="12" cy="12" r="5"></circle>
      <line x1="12" y1="1" x2="12" y2="3"></line>
      <line x1="12" y1="21" x2="12" y2="23"></line>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
      <line x1="1" y1="12" x2="3" y2="12"></line>
      <line x1="21" y1="12" x2="23" y2="12"></line>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
    `;
  }
}

themeToggle.addEventListener('click', () => {
  const currentTheme = html.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', newTheme);
  localStorage.setItem('gas-theme', newTheme);
  updateThemeIcon(newTheme);
});

// Remove no-transition class after page load
window.addEventListener('DOMContentLoaded', () => {
  requestAnimationFrame(() => {
    document.body.classList.remove('no-theme-transition');
  });
});

// =============================================================================
// Utility Functions
// =============================================================================

function formatElapsed(startTimeStr) {
  if (!startTimeStr) return '--:--:--';
  const start = new Date(startTimeStr);
  const now = new Date();
  const diff = Math.floor((now - start) / 1000);

  if (diff < 0) return '00:00:00';

  const hours = Math.floor(diff / 3600);
  const minutes = Math.floor((diff % 3600) / 60);
  const seconds = diff % 60;

  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// =============================================================================
// Connection Status
// =============================================================================

function updateConnectionStatus(connected) {
  const statusEl = document.getElementById('connection-status');
  const textEl = document.getElementById('connection-text');

  if (connected) {
    statusEl.classList.add('connected');
    statusEl.classList.remove('disconnected');
    textEl.textContent = 'Connected';
  } else {
    statusEl.classList.remove('connected');
    statusEl.classList.add('disconnected');
    textEl.textContent = 'Disconnected';
  }
  connectionOk = connected;
}

// =============================================================================
// API Fetch
// =============================================================================

async function fetchStatus() {
  try {
    const response = await fetch('/api/status');
    gasData = await response.json();
    updateDashboard(gasData);
    updateConnectionStatus(true);

    if (selectedAgent && gasData.agents && gasData.agents[selectedAgent]) {
      updateDetailPanel(selectedAgent, gasData.agents[selectedAgent]);
    }
  } catch (error) {
    console.error('Error fetching status:', error);
    updateConnectionStatus(false);
  }
}

// =============================================================================
// Dashboard Update
// =============================================================================

function updateDashboard(data) {
  // Update header info
  document.getElementById('project-name').textContent = data.project_name || 'GAS Project';
  document.getElementById('task-objective').textContent = data.task_objective || '';
  document.getElementById('gas-mode').textContent = data.mode || 'swarm';
  document.getElementById('current-wave').textContent = data.current_wave || 1;
  document.getElementById('elapsed-time').textContent = formatElapsed(data.start_time);
  document.getElementById('last-updated').textContent = 'Just now';

  // Update stats bar
  document.getElementById('total-agents').textContent = data.total_agents || 0;
  document.getElementById('total-generations').textContent = data.total_generations || 0;

  const patternsCount = (data.knowledge?.success_patterns || 0) + (data.knowledge?.anti_patterns || 0);
  document.getElementById('patterns-count').textContent = patternsCount;
  document.getElementById('successions-count').textContent = data.successions?.length || 0;
  document.getElementById('running-count').textContent = data.running_agents || 0;
  document.getElementById('completed-count').textContent = data.completed_agents || 0;

  // Update overall progress
  const progress = data.overall_progress || 0;
  document.getElementById('overall-percentage').textContent = Math.round(progress) + '%';
  const progressBar = document.getElementById('overall-progress');
  progressBar.style.width = progress + '%';

  if (progress >= 100) {
    progressBar.classList.add('complete');
    progressBar.classList.remove('active');
    document.getElementById('overall-percentage').classList.add('complete');
    document.getElementById('pulse-indicator').classList.add('completed');
  } else {
    progressBar.classList.remove('complete');
    progressBar.classList.add('active');
    document.getElementById('overall-percentage').classList.remove('complete');
    document.getElementById('pulse-indicator').classList.remove('completed');
  }

  // Update knowledge sidebar
  document.getElementById('success-patterns').textContent = data.knowledge?.success_patterns || 0;
  document.getElementById('anti-patterns').textContent = data.knowledge?.anti_patterns || 0;
  document.getElementById('domain-insights').textContent = data.knowledge?.domain_insights || 0;

  // Update succession list
  updateSuccessionList(data.successions || []);

  // Update waves and agents
  updateWavesAndAgents(data);
}

// =============================================================================
// Succession Events List
// =============================================================================

function updateSuccessionList(successions) {
  const container = document.getElementById('succession-list');

  if (!successions || successions.length === 0) {
    container.innerHTML = '<p class="empty-state-small">No successions yet</p>';
    return;
  }

  container.innerHTML = successions.slice(-10).reverse().map(s => `
    <div class="succession-item">
      <span class="succession-agent">${escapeHtml(s.agent)}</span>
      <span class="succession-arrow">G${s.from_gen} &rarr; G${s.to_gen}</span>
      <span class="succession-reason">${escapeHtml(s.reason || '')}</span>
    </div>
  `).join('');
}

// =============================================================================
// Waves and Agents Grid
// =============================================================================

function updateWavesAndAgents(data) {
  const container = document.getElementById('waves-container');

  if (!data.agents || Object.keys(data.agents).length === 0) {
    container.innerHTML = '<p class="empty-state">No agents found</p>';
    return;
  }

  // Group agents by wave
  const waves = data.waves || {};
  const agentsByWave = {};

  // Initialize waves from wave data
  Object.entries(waves).forEach(([waveNum, waveData]) => {
    agentsByWave[waveNum] = {
      agents: [],
      completed: waveData.completed || false,
      in_progress: waveData.in_progress || false
    };
  });

  // Group agents by their wave
  Object.entries(data.agents).forEach(([agentId, agent]) => {
    const wave = agent.wave || 1;
    if (!agentsByWave[wave]) {
      agentsByWave[wave] = { agents: [], completed: false, in_progress: false };
    }
    agentsByWave[wave].agents.push({ id: agentId, ...agent });
  });

  // Calculate wave status
  Object.entries(agentsByWave).forEach(([waveNum, waveData]) => {
    waveData.completed = waveData.agents.every(a => a.status === 'completed');
    waveData.in_progress = waveData.agents.some(a => a.status === 'running');
  });

  // Sort waves by number
  const sortedWaves = Object.entries(agentsByWave).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));

  if (sortedWaves.length === 0) {
    container.innerHTML = '<p class="empty-state">No waves found</p>';
    return;
  }

  container.innerHTML = sortedWaves.map(([waveNum, waveData]) => {
    const waveStatus = waveData.completed ? 'completed' : (waveData.in_progress ? 'running' : 'pending');

    const agentsHtml = waveData.agents.map(agent => createAgentCardHtml(agent)).join('');

    return `
      <div class="wave-section ${waveStatus}">
        <div class="wave-header">
          <h2 class="wave-title">Wave ${waveNum}</h2>
          <span class="status-badge ${waveStatus}">${waveStatus}</span>
        </div>
        <div class="agents-grid">
          ${agentsHtml || '<p class="empty-state">No agents in this wave</p>'}
        </div>
      </div>
    `;
  }).join('');

  // Add click handlers to agent cards
  document.querySelectorAll('.agent-card').forEach(card => {
    card.addEventListener('click', (e) => {
      const agentId = card.dataset.agentId;
      if (agentId) {
        selectAgent(agentId);
      }
    });
  });
}

// =============================================================================
// Agent Card Creation
// =============================================================================

function createAgentCardHtml(agent) {
  const agentId = agent.id;
  const status = agent.status || 'pending';
  const isSelected = selectedAgent === agentId;

  // Create generation badges
  const generations = agent.generations || [];
  let genBadges = '';

  if (generations.length > 0) {
    genBadges = generations.map(gen => {
      const genStatus = gen.status || 'pending';
      return `<span class="gen-badge ${genStatus}">G${gen.generation}</span>`;
    }).join('');
  } else if (agent.current_generation) {
    // Fallback: show current generation if no generations array
    const currentGen = agent.current_generation;
    const totalGens = agent.total_generations || currentGen;
    for (let i = 1; i <= totalGens; i++) {
      const genStatus = i < currentGen ? 'completed' : (i === currentGen ? status : 'pending');
      genBadges += `<span class="gen-badge ${genStatus}">G${i}</span>`;
    }
  } else {
    genBadges = '<span class="gen-badge running">G1</span>';
  }

  const progress = agent.progress || 0;

  return `
    <div class="agent-card ${status}${isSelected ? ' selected' : ''}" data-agent-id="${escapeHtml(agentId)}">
      <div class="agent-card__header">
        <span class="agent-card__role">${escapeHtml(agent.role || agentId)}</span>
        <span class="status-badge ${status}">${status}</span>
      </div>
      <div class="agent-card__generations">
        ${genBadges}
      </div>
      <div class="agent-card__progress">
        <div class="agent-card__progress-fill ${status}" style="width: ${progress}%"></div>
      </div>
      <div class="agent-card__meta">
        <span>Gen ${agent.current_generation || 1}/${agent.total_generations || 1}</span>
        <span>${progress}%</span>
      </div>
    </div>
  `;
}

// =============================================================================
// Agent Selection & Detail Panel
// =============================================================================

function selectAgent(agentId) {
  selectedAgent = agentId;

  document.getElementById('app').classList.add('detail-open');
  document.getElementById('detail-panel').classList.add('open');
  document.getElementById('detail-panel').setAttribute('aria-hidden', 'false');

  // Update card selection state
  document.querySelectorAll('.agent-card').forEach(card => {
    card.classList.remove('selected');
    if (card.dataset.agentId === agentId) {
      card.classList.add('selected');
    }
  });

  // Update detail panel
  if (gasData && gasData.agents && gasData.agents[agentId]) {
    updateDetailPanel(agentId, gasData.agents[agentId]);
  }
}

function closeDetailPanel() {
  selectedAgent = null;
  document.getElementById('app').classList.remove('detail-open');
  document.getElementById('detail-panel').classList.remove('open');
  document.getElementById('detail-panel').setAttribute('aria-hidden', 'true');

  document.querySelectorAll('.agent-card').forEach(card => {
    card.classList.remove('selected');
  });
}

function updateDetailPanel(agentId, agent) {
  document.getElementById('detail-title').textContent = agent.role || agentId;
  document.getElementById('detail-subtitle').textContent = agentId;

  const content = document.getElementById('detail-content');

  // Build generations timeline
  const generations = agent.generations || [];
  let timelineHtml = '';

  if (generations.length > 0) {
    timelineHtml = `
      <div class="generations-timeline">
        ${generations.map(gen => `
          <div class="timeline-item ${gen.status || 'pending'}">
            <div class="timeline-marker"></div>
            <div class="timeline-content">
              <span class="timeline-title">Generation ${gen.generation}</span>
              <span class="timeline-status">${gen.status || 'pending'}</span>
              ${gen.confidence !== undefined ? `<span class="timeline-confidence">Confidence: ${Math.round(gen.confidence * 100)}%</span>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } else {
    timelineHtml = '<p style="color: var(--color-text-secondary)">No generation history available</p>';
  }

  // Activity feed (if available from extended data)
  let activityHtml = '<p style="color: var(--color-text-secondary); padding: var(--space-3);">No activity data available</p>';
  if (agent.live_events && agent.live_events.length > 0) {
    activityHtml = agent.live_events.slice(-20).reverse().map(event => {
      const iconClass = event.type === 'tool' || event.type === 'tool_use' ? 'tool' :
                       event.type === 'thinking' ? 'thinking' : 'result';
      return `
        <div class="activity-item">
          <div class="activity-icon ${iconClass}">&#9889;</div>
          <div class="activity-content">
            ${event.tool ? `<span class="activity-tool">${escapeHtml(event.tool)}</span>` : ''}
            <div class="activity-text">${escapeHtml(event.content || '')}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  // Files created (if available)
  let filesHtml = '<p style="color: var(--color-text-secondary); padding: var(--space-3);">No files created yet</p>';
  if (agent.files_created && agent.files_created.length > 0) {
    filesHtml = agent.files_created.map(file => `
      <div class="file-item">
        <span class="file-icon">&#128196;</span>
        <span>${escapeHtml(file)}</span>
      </div>
    `).join('');
  }

  content.innerHTML = `
    <div class="detail-section">
      <h3 class="detail-section-title">Status</h3>
      <div class="detail-info-grid">
        <div class="detail-info-item">
          <div class="detail-info-label">Status</div>
          <div class="detail-info-value">${agent.status || 'Unknown'}</div>
        </div>
        <div class="detail-info-item">
          <div class="detail-info-label">Progress</div>
          <div class="detail-info-value">${agent.progress || 0}%</div>
        </div>
        <div class="detail-info-item">
          <div class="detail-info-label">Wave</div>
          <div class="detail-info-value">${agent.wave || 1}</div>
        </div>
        <div class="detail-info-item">
          <div class="detail-info-label">Generation</div>
          <div class="detail-info-value">${agent.current_generation || 1}/${agent.total_generations || 1}</div>
        </div>
      </div>
    </div>

    <div class="detail-section">
      <h3 class="detail-section-title">Generations Timeline</h3>
      ${timelineHtml}
    </div>

    <div class="detail-section">
      <h3 class="detail-section-title">Files Created</h3>
      <div class="files-list">${filesHtml}</div>
    </div>

    <div class="detail-section">
      <h3 class="detail-section-title">Live Activity Feed</h3>
      <div class="activity-feed">${activityHtml}</div>
    </div>
  `;
}

// =============================================================================
// Keyboard Navigation
// =============================================================================

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && selectedAgent) {
    closeDetailPanel();
  }
});

// =============================================================================
// Initialize
// =============================================================================

initTheme();
fetchStatus();
setInterval(fetchStatus, 2000);
  </script>
</html>'''

# =============================================================================
# FilePositionTracker (from v6 - for incremental reads)
# =============================================================================

class FilePositionTracker:
    """Tracks file positions for incremental reading."""

    def __init__(self):
        self._positions: Dict[str, int] = {}
        self._sizes: Dict[str, int] = {}
        self._mtimes: Dict[str, float] = {}

    def get_new_content(self, filepath: str) -> Optional[str]:
        """Get only new content since last read."""
        if not os.path.exists(filepath):
            return None
        try:
            stat = os.stat(filepath)
            current_size = stat.st_size
            current_mtime = stat.st_mtime

            last_pos = self._positions.get(filepath, 0)
            last_size = self._sizes.get(filepath, 0)
            last_mtime = self._mtimes.get(filepath, 0)

            # File was truncated/recreated - reset position
            if current_size < last_size:
                last_pos = 0

            # No changes
            if current_mtime == last_mtime and current_size == last_size:
                return None

            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_pos)
                content = f.read()
                new_pos = f.tell()

            self._positions[filepath] = new_pos
            self._sizes[filepath] = current_size
            self._mtimes[filepath] = current_mtime

            return content
        except Exception as e:
            logger.error(f"Error reading new content from {filepath}: {e}")
            return None

    def reset(self, filepath: Optional[str] = None):
        """Reset tracking for a file or all files."""
        if filepath:
            self._positions.pop(filepath, None)
            self._sizes.pop(filepath, None)
            self._mtimes.pop(filepath, None)
        else:
            self._positions.clear()
            self._sizes.clear()
            self._mtimes.clear()

    def get_full_content(self, filepath: str) -> Optional[str]:
        """Get full file content and update position tracker."""
        if not os.path.exists(filepath):
            return None
        try:
            stat = os.stat(filepath)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            self._positions[filepath] = stat.st_size
            self._sizes[filepath] = stat.st_size
            self._mtimes[filepath] = stat.st_mtime
            return content
        except Exception as e:
            logger.error(f"Error reading full content from {filepath}: {e}")
            return None


# Global file tracker instance
file_tracker = FilePositionTracker()

# =============================================================================
# BoundedParseCache (from v6 - LRU cache for parsed results)
# =============================================================================

class BoundedParseCache:
    """LRU-style cache for parsed output results."""

    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self._cache: Dict[Tuple[str, float], Dict[str, Any]] = {}
        self._max_size = max_size

    def get(self, filepath: str, mtime: float) -> Optional[Dict[str, Any]]:
        """Get cached result if available."""
        return self._cache.get((filepath, mtime))

    def put(self, filepath: str, mtime: float, result: Dict[str, Any]):
        """Store result in cache with LRU eviction."""
        key = (filepath, mtime)
        # Evict oldest if at capacity
        if len(self._cache) >= self._max_size and key not in self._cache:
            oldest_key = min(self._cache.keys(), key=lambda k: k[1])
            del self._cache[oldest_key]
        self._cache[key] = result

    def invalidate(self, filepath: Optional[str] = None):
        """Invalidate cache for a file or all files."""
        if filepath:
            keys_to_remove = [k for k in self._cache.keys() if k[0] == filepath]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Current cache size."""
        return len(self._cache)


# Global parse cache instance
parse_cache = BoundedParseCache()

# =============================================================================
# Line-by-Line JSON Parser (from v6 - replaces regex)
# =============================================================================

def parse_json_lines(content: str) -> List[Dict[str, Any]]:
    """Parse content as newline-delimited JSON."""
    events = []
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def extract_tool_usage(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """Extract tool usage statistics from parsed events."""
    tools_used: Dict[str, int] = {}
    for event in events:
        # Direct tool name
        if 'name' in event:
            tool_name = event['name']
            tools_used[tool_name] = tools_used.get(tool_name, 0) + 1
        # Tool use in assistant message content
        if event.get('type') == 'assistant' and 'message' in event:
            msg = event['message']
            if 'content' in msg and isinstance(msg['content'], list):
                for item in msg['content']:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        tool_name = item.get('name', 'unknown')
                        tools_used[tool_name] = tools_used.get(tool_name, 0) + 1
    return tools_used


def extract_live_events(events: List[Dict[str, Any]], max_events: int = MAX_LIVE_EVENTS) -> List[Dict[str, Any]]:
    """Extract live events with timestamp preservation."""
    live_events: List[Dict[str, Any]] = []

    for event in events[-max_events * 2:]:  # Process more to account for expansion
        live_event = {
            'type': event.get('type', 'unknown'),
            'tool': event.get('name', ''),
            'content': str(event.get('content', ''))[:MAX_CONTENT_LENGTH],
            'timestamp': event.get('timestamp'),
            'uuid': event.get('uuid')
        }

        # Handle assistant messages with tool_use or text content
        if event.get('type') == 'assistant' and 'message' in event:
            msg = event['message']
            if 'content' in msg and isinstance(msg['content'], list):
                for item in msg['content']:
                    if isinstance(item, dict):
                        if item.get('type') == 'tool_use':
                            live_events.append({
                                'type': 'tool',
                                'tool': item.get('name', ''),
                                'content': str(item.get('input', ''))[:MAX_CONTENT_LENGTH],
                                'timestamp': event.get('timestamp'),
                                'uuid': item.get('id')
                            })
                        elif item.get('type') == 'text':
                            text_content = str(item.get('text', ''))[:MAX_CONTENT_LENGTH]
                            if text_content.strip():
                                live_events.append({
                                    'type': 'thinking',
                                    'tool': '',
                                    'content': text_content,
                                    'timestamp': event.get('timestamp'),
                                    'uuid': event.get('uuid')
                                })
        else:
            # Add direct event if it has meaningful content
            if live_event['content'] or live_event['tool']:
                live_events.append(live_event)

    return live_events[-max_events:]


def extract_files_created(events: List[Dict[str, Any]], max_files: int = MAX_FILES_CREATED) -> List[str]:
    """Extract list of files created from events."""
    files: set = set()

    for event in events:
        # Direct tool events
        if event.get('name') in ('Write', 'Edit', 'NotebookEdit'):
            input_data = event.get('input', {})
            if isinstance(input_data, dict):
                filepath = input_data.get('file_path') or input_data.get('notebook_path')
                if filepath:
                    files.add(filepath)

        # Tool use in assistant message content
        if event.get('type') == 'assistant' and 'message' in event:
            msg = event['message']
            if 'content' in msg and isinstance(msg['content'], list):
                for item in msg['content']:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        if item.get('name') in ('Write', 'Edit', 'NotebookEdit'):
                            input_data = item.get('input', {})
                            if isinstance(input_data, dict):
                                filepath = input_data.get('file_path') or input_data.get('notebook_path')
                                if filepath:
                                    files.add(filepath)

    return list(files)[:max_files]

# =============================================================================
# Helper Functions
# =============================================================================

def read_json_file(filepath: str) -> Optional[Dict[str, Any]]:
    """Safely read and parse a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
        logger.debug(f"Could not read JSON file {filepath}: {e}")
        return None


def get_file_mtime(filepath: str) -> Optional[datetime]:
    """Get file modification time as datetime."""
    try:
        if os.path.islink(filepath):
            real_path = os.path.realpath(filepath)
            if os.path.exists(real_path):
                return datetime.fromtimestamp(os.path.getmtime(real_path), tz=timezone.utc)
        if os.path.exists(filepath):
            return datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc)
    except Exception:
        pass
    return None


def format_time_ago(dt: Optional[datetime]) -> str:
    """Format datetime as human-readable 'X ago' string."""
    if not dt:
        return "Unknown"
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 0:
        return "Just now"
    elif seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    elif seconds < 86400:
        return f"{seconds // 3600}h ago"
    else:
        return f"{seconds // 86400}d ago"


def format_elapsed_time(start_time_str: str) -> str:
    """Format elapsed time as human-readable string."""
    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=start_time.tzinfo)
        elapsed = now - start_time
        total_seconds = int(elapsed.total_seconds())

        if total_seconds < 0:
            return "0s"

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "Unknown"

# =============================================================================
# Agent Output Parser (combines v6 line-by-line parsing with GAS data)
# =============================================================================

def parse_agent_output(output_file: Optional[str], use_cache: bool = True) -> Dict[str, Any]:
    """Parse agent output file with v6 performance improvements."""
    result = {
        'tools_used': {},
        'last_activity': None,
        'activity': 'Working...',
        'progress': 0,
        'is_complete': False,
        'total_events': 0,
        'files_created': [],
        'live_events': []
    }

    if not output_file or not os.path.exists(output_file):
        return result

    try:
        mtime = os.path.getmtime(output_file)
        result['last_activity'] = datetime.fromtimestamp(mtime, tz=timezone.utc)

        # Check cache first
        if use_cache:
            cached = parse_cache.get(output_file, mtime)
            if cached is not None:
                return cached

        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        if not content:
            return result

        # Check completion markers
        for marker in COMPLETION_MARKERS:
            if marker in content:
                result['is_complete'] = True
                result['progress'] = 100
                break

        # Parse JSON lines (v6 improvement)
        events = parse_json_lines(content)
        result['tools_used'] = extract_tool_usage(events)
        result['total_events'] = len(events)

        # Get activity text from last meaningful line
        lines = content.strip().split('\n')
        if lines:
            for line in reversed(lines[-10:]):
                if len(line) > 10 and not line.startswith('{'):
                    result['activity'] = line[:100] + ('...' if len(line) > 100 else '')
                    break

        # Estimate progress if not complete
        if not result['is_complete']:
            total_tools = sum(result['tools_used'].values())
            result['progress'] = min(95, total_tools * 5)

        # Extract files and live events
        result['files_created'] = extract_files_created(events)
        result['live_events'] = extract_live_events(events)

        # Cache result
        if use_cache:
            parse_cache.put(output_file, mtime, result)

        return result

    except Exception as e:
        logger.error(f"Error parsing output: {e}")
        return result

# =============================================================================
# GAS-Specific Functions (from current-gas.py)
# =============================================================================

def get_agent_generations(agent_dir: str) -> List[Dict[str, Any]]:
    """Get all generations for an agent."""
    generations = []
    gen_base = os.path.join(agent_dir, 'generations')

    if not os.path.isdir(gen_base):
        return generations

    try:
        for item in os.listdir(gen_base):
            if item.startswith('gen-'):
                try:
                    gen_num = int(item.replace('gen-', ''))
                    gen_dir = os.path.join(gen_base, item)
                    status_file = os.path.join(gen_dir, 'status.json')
                    status = read_json_file(status_file) or {
                        'generation': gen_num,
                        'status': 'pending',
                        'progress': 0,
                        'confidence': 1.0
                    }
                    generations.append(status)
                except ValueError:
                    pass
    except PermissionError:
        pass

    return sorted(generations, key=lambda x: x.get('generation', 0))


def get_agent_status(agent_id: str, agent_config: Dict[str, Any], gas_dir: str) -> Dict[str, Any]:
    """Get status of a single agent including all its generations."""
    agent_dir = os.path.join(gas_dir, 'agents', agent_id)

    # Default agent info
    agent_info = {
        'id': agent_id,
        'role': agent_config.get('role', agent_id),
        'wave': agent_config.get('wave', 1),
        'status': 'pending',
        'current_generation': agent_config.get('current_generation', 0),
        'total_generations': agent_config.get('total_generations', 0),
        'progress': 0,
        'generations': [],
        'mission': agent_config.get('mission', ''),
        # v6 additions
        'tools_used': {},
        'live_events': [],
        'files_created': [],
        'total_events': 0,
        'last_activity_ago': 'Never',
        'is_idle': False,
        'activity': 'Waiting...'
    }

    # Check agent status file
    status_file = os.path.join(agent_dir, 'status.json')
    agent_status = read_json_file(status_file)
    if agent_status:
        agent_info.update({
            'status': agent_status.get('status', 'running'),
            'progress': agent_status.get('progress', 0),
            'current_generation': agent_status.get('generation', 1)
        })

    # Get all generations for this agent
    generations = get_agent_generations(agent_dir)
    agent_info['generations'] = generations
    agent_info['total_generations'] = len(generations)

    # Calculate overall progress from latest generation
    if generations:
        latest = max(generations, key=lambda x: x.get('generation', 0))
        agent_info['progress'] = latest.get('progress', 0)
        agent_info['status'] = latest.get('status', 'running')
        agent_info['current_generation'] = latest.get('generation', 1)

    # Try to find and parse output file for v6 features
    output_file = None
    task_id = agent_config.get('task_id')

    # Check multiple possible output locations
    possible_output_paths = [
        os.path.join(agent_dir, 'output.jsonl'),
        os.path.join(agent_dir, 'agent.output'),
    ]

    if task_id:
        task_dir = os.getenv('TASK_DIR', '/tmp/claude-1000')
        possible_output_paths.insert(0, os.path.join(task_dir, f'{task_id}.output'))

    for path in possible_output_paths:
        if os.path.exists(path):
            output_file = path
            break

    # Also check for any .output file in agent dir
    if not output_file:
        pattern = os.path.join(agent_dir, '*.output')
        matches = glob.glob(pattern)
        if matches:
            output_file = matches[0]

    # Parse output file for v6 features
    if output_file:
        parsed = parse_agent_output(output_file)
        agent_info['tools_used'] = parsed['tools_used']
        agent_info['live_events'] = parsed['live_events']
        agent_info['files_created'] = parsed['files_created']
        agent_info['total_events'] = parsed['total_events']
        agent_info['activity'] = parsed['activity']

        if parsed['last_activity']:
            agent_info['last_activity_ago'] = format_time_ago(parsed['last_activity'])

            # Determine status based on activity with idle detection
            now = datetime.now(timezone.utc)
            seconds_idle = (now - parsed['last_activity']).total_seconds()

            if parsed['is_complete'] or agent_info['status'] == 'completed':
                agent_info['status'] = 'completed'
                agent_info['progress'] = 100
                agent_info['is_idle'] = False
            elif seconds_idle > COMPLETION_THRESHOLD_SECONDS:
                # Long idle - likely completed
                agent_info['status'] = 'completed'
                agent_info['progress'] = 100
                agent_info['is_idle'] = False
            elif seconds_idle > IDLE_THRESHOLD_SECONDS:
                # Short idle - agent may be stuck
                agent_info['status'] = 'idle'
                agent_info['is_idle'] = True
            else:
                # Active
                if agent_info['status'] not in ('completed', 'failed'):
                    agent_info['status'] = 'running'
                agent_info['is_idle'] = False

            # Update progress from parsed data if not complete
            if agent_info['status'] != 'completed' and parsed['progress'] > agent_info['progress']:
                agent_info['progress'] = parsed['progress']

    return agent_info


def get_knowledge_store(gas_dir: str) -> Dict[str, Any]:
    """Get accumulated knowledge statistics."""
    store_path = os.path.join(gas_dir, 'knowledge', 'store.json')
    store = read_json_file(store_path)

    if not store:
        return {
            'success_patterns': 0,
            'anti_patterns': 0,
            'domain_insights': 0,
            'total_generations': 0,
            'patterns': [],
            'agent_contributions': {}
        }

    # Count contributions by agent
    agent_contributions: Dict[str, int] = {}
    for pattern in store.get('success_patterns', []):
        agent = pattern.get('source_agent', 'unknown')
        agent_contributions[agent] = agent_contributions.get(agent, 0) + 1

    return {
        'success_patterns': len(store.get('success_patterns', [])),
        'anti_patterns': len(store.get('anti_patterns', [])),
        'domain_insights': len(store.get('domain_knowledge', [])),
        'total_generations': store.get('total_generations_across_swarm', 0),
        'patterns': store.get('success_patterns', [])[:5],  # Top 5 for display
        'agent_contributions': agent_contributions
    }


def get_gas_status() -> Dict[str, Any]:
    """Gather complete GAS status with v6 enhancements."""
    # Read GAS state
    state_path = os.path.join(GAS_DIR, 'gas-state.json')
    state = read_json_file(state_path) or {
        'project_name': GAS_NAME,
        'start_time': SERVER_START_TIME,
        'mode': GAS_MODE,
        'task_objective': 'Unknown',
        'swarm': {'waves': {}, 'current_wave': 1},
        'agents': {}
    }

    # Get agent statuses
    agents: Dict[str, Dict[str, Any]] = {}
    agents_config = state.get('agents', {})

    for agent_id, agent_config in agents_config.items():
        agents[agent_id] = get_agent_status(agent_id, agent_config, GAS_DIR)

    # Organize by waves
    waves = state.get('swarm', {}).get('waves', {})
    wave_status: Dict[str, Dict[str, Any]] = {}
    for wave_num, wave_agents in waves.items():
        wave_status[wave_num] = {
            'agents': wave_agents,
            'completed': all(
                agents.get(a, {}).get('status') == 'completed'
                for a in wave_agents
            ),
            'in_progress': any(
                agents.get(a, {}).get('status') == 'running'
                for a in wave_agents
            )
        }

    # Get knowledge statistics
    knowledge = get_knowledge_store(GAS_DIR)

    # Calculate aggregates
    total_agents = len(agents)
    completed_agents = sum(1 for a in agents.values() if a['status'] == 'completed')
    running_agents = sum(1 for a in agents.values() if a['status'] == 'running')
    failed_agents = sum(1 for a in agents.values() if a['status'] == 'failed')
    pending_agents = sum(1 for a in agents.values() if a['status'] == 'pending')
    idle_agents = sum(1 for a in agents.values() if a['status'] == 'idle')
    total_generations = sum(a.get('total_generations', 0) for a in agents.values())

    # Succession events
    successions = []
    for agent_id, agent in agents.items():
        for i, gen in enumerate(agent.get('generations', [])[:-1]):
            if gen.get('status') in ['completed', 'needs_succession']:
                successions.append({
                    'agent': agent_id,
                    'from_gen': gen.get('generation', i + 1),
                    'to_gen': gen.get('generation', i + 1) + 1,
                    'reason': gen.get('succession_reason', 'unknown')
                })

    # Overall progress (average of all agent progress)
    if agents:
        overall_progress = sum(a.get('progress', 0) for a in agents.values()) / len(agents)
    else:
        overall_progress = 0

    return {
        # GAS data
        'project_name': state.get('project_name', GAS_NAME),
        'gas_name': state.get('project_name', GAS_NAME),  # Alias for compatibility
        'swarm_name': state.get('project_name', GAS_NAME),  # v6 compatibility
        'task_objective': state.get('task_objective', ''),
        'mode': state.get('mode', GAS_MODE),
        'start_time': state.get('start_time', SERVER_START_TIME),
        'current_wave': state.get('swarm', {}).get('current_wave', 1),
        'agents': agents,
        'waves': wave_status,
        'knowledge': knowledge,
        'successions': successions,

        # Status counts (v6 style)
        'overall_progress': round(overall_progress, 1),
        'total_agents': total_agents,
        'completed_agents': completed_agents,
        'running_agents': running_agents,
        'total_generations': total_generations,

        # v6 count aliases
        'running_count': running_agents,
        'completed_count': completed_agents,
        'pending_count': pending_agents,
        'failed_count': failed_agents,
        'idle_count': idle_agents,

        # Timestamps
        'elapsed_time': format_elapsed_time(state.get('start_time', SERVER_START_TIME)),
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }

# =============================================================================
# HTTP Handler (GAS style with v6 endpoints)
# =============================================================================

class GASHandler(BaseHTTPRequestHandler):
    """HTTP request handler for GAS Dashboard."""

    def log_message(self, format, *args):
        """Custom logging."""
        logger.info("%s - %s", self.address_string(), format % args)

    def send_cors_headers(self):
        """Send CORS headers for cross-origin requests."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def send_json(self, data: Any, status: int = 200):
        """Send JSON response."""
        json_data = json.dumps(data, indent=2)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(json_data.encode('utf-8')))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json_data.encode('utf-8'))

    def send_html(self, html: str, status: int = 200):
        """Send HTML response."""
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html.encode('utf-8')))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def do_OPTIONS(self):
        """Handle OPTIONS request for CORS preflight."""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        try:
            if path == '/' or path == '/index.html':
                self.send_html(DASHBOARD_HTML)
            elif path == '/api/status':
                self.send_json(get_gas_status())
            elif path.startswith('/api/agent/'):
                agent_id = path.replace('/api/agent/', '')
                status = get_gas_status()
                if agent_id in status['agents']:
                    self.send_json(status['agents'][agent_id])
                else:
                    self.send_json({'error': 'Agent not found'}, 404)
            elif path == '/health':
                self.send_json({
                    'status': 'healthy',
                    'version': 'gas-v6-combined',
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'cache_size': parse_cache.size
                })
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            logger.error(f"Error handling request {path}: {e}")
            self.send_json({'error': str(e)}, 500)

# =============================================================================
# Server Entry Point
# =============================================================================

def run_server(port: int = PORT):
    """Run the GAS Dashboard server."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, GASHandler)

    def signal_handler(signum, frame):
        logger.info("Shutting down GAS Dashboard...")
        httpd.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("GAS Dashboard Server (v6 Performance + GAS Data)")
    logger.info("=" * 60)
    logger.info(f"Port: {port}")
    logger.info(f"GAS_DIR: {GAS_DIR}")
    logger.info(f"GAS_MODE: {GAS_MODE}")
    logger.info(f"Project: {GAS_NAME}")
    logger.info(f"Idle Threshold: {IDLE_THRESHOLD_SECONDS}s")
    logger.info(f"Completion Threshold: {COMPLETION_THRESHOLD_SECONDS}s")
    logger.info(f"Max Cache Size: {MAX_CACHE_SIZE}")
    logger.info("=" * 60)
    logger.info(f"Dashboard: http://localhost:{port}/")
    logger.info(f"API Status: http://localhost:{port}/api/status")
    logger.info(f"API Agent: http://localhost:{port}/api/agent/<id>")
    logger.info(f"Health: http://localhost:{port}/health")
    logger.info("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        httpd.server_close()
        logger.info("Server stopped.")


if __name__ == '__main__':
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)

    run_server(port)
