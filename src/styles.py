"""Application-wide GTK styling."""
from typography import FONT_FAMILY, FONT_SIZES

CSS = b"""
* { font-family: __FONT_FAMILY__, sans-serif; }
window { background: #000000; color: #f4f5f8; }
window .main-content { background: #000000; }
window .sidebar { background: #050505; border-right: 1px solid #232833; padding: 14px 9px; }
window .brand { padding: 8px 4px 16px; }
window .brand-mark { color: #ff334f; font-size: 26px; font-weight: 900; }
window .brand-title { color: #f4f5f8; font-size: 12px; font-weight: 800; letter-spacing: 0.4px; }
window button.nav { min-height: 46px; border-radius: 3px; margin: 2px 0; color: #9da4b2; background: transparent; border: 1px solid transparent; box-shadow: none; font-size: 15px; }
window button.nav:checked { background: rgba(229, 43, 69, 0.14); border-color: rgba(255, 64, 89, 0.55); color: #fff; box-shadow: none; }
window button.nav:hover { background: #191d25; color: #fff; }
window .nav-section { color: #68707d; font-size: 9px; font-weight: 800; letter-spacing: 1.6px; padding: 12px 10px 3px; }
window .page-title { font-size: 28px; font-weight: 800; color: #f8f8fa; }
window .eyebrow { font-size: 10px; font-weight: 800; letter-spacing: 2px; color: #ff5268; }
window .subtle { color: #9097a5; }
window .surface.hero { background: #101114; border: 0; border-radius: 0; padding: 22px; }
window .hero-title { font-size: 23px; font-weight: 800; }
window .hero-device { font-size: 27px; font-weight: 900; }
window .hero-tag { color: #9aa2b1; font-size: 10px; font-weight: 800; letter-spacing: 2px; }
window .hero-spec { color: #c3c9d4; font-size: 12px; }
window .hero-value { font-size: 13px; font-weight: 900; color: #ff465d; letter-spacing: 2px; }
window .surface { background: #151820; border: 1px solid #292e39; border-radius: 12px; padding: 17px; }
window .surface-title { color: #858d9c; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }
window .surface-value { color: #f4f5f8; font-size: 21px; font-weight: 750; }
window button.profile-card { background: #151820; border: 1px solid #2a2f39; border-radius: 12px; padding: 16px; box-shadow: none; }
window button.profile-card:hover { border-color: #777f8e; background: #1b1e27; box-shadow: none; }
window button.profile-card.active { border: 1px solid #ff4059; background: #26161c; box-shadow: none; }
window button.quick-link { background: #151820; border: 1px solid #292e39; border-radius: 9px; color: #e9ebef; padding: 11px 14px; box-shadow: none; }
window button.quick-link:hover { background: #1b1e27; border-color: #555d6b; color: #fff; box-shadow: none; }
window .profile-symbol { font-size: 20px; color: #ff465d; font-weight: 900; }
window .profile-badge { min-width: 46px; min-height: 46px; border-radius: 999px; background: rgba(229, 43, 69, 0.10); border: 1px solid rgba(229, 43, 69, 0.45); }
window button.profile-card.active .profile-badge { background: rgba(229, 43, 69, 0.22); border-color: #ff4059; }
window .battery-hero { background: linear-gradient(110deg, #11151c, #171b22); border: 1px solid #303641; border-radius: 12px; padding: 22px; }
window .battery-hero-title { font-size: 24px; font-weight: 850; }
window .battery-hero-copy { color: #a7afbd; font-size: 12px; }
window .battery-hero-note { color: #6f7887; font-size: 10px; }
window .battery-visual { min-width: 250px; min-height: 190px; }
window .battery-visual-value { font-size: 30px; font-weight: 900; color: #f4f5f8; }
window .battery-visual-label { color: #8c95a4; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }
window button.battery-mode-card { min-height: 86px; padding: 14px 18px; background: #11151c; border: 1px solid #303641; border-radius: 9px; color: #f4f5f8; box-shadow: none; }
window button.battery-mode-card:hover { background: #1b1e27; border-color: #68707d; box-shadow: none; }
window button.battery-mode-card.active { background: linear-gradient(90deg, rgba(229,43,69,.22), rgba(37,22,28,.72)); border: 1px solid #ff4059; box-shadow: inset 3px 0 #ff4059; }
window .battery-mode-icon { min-width: 30px; min-height: 30px; border-radius: 999px; color: #737d8d; background: #202630; font-size: 14px; font-weight: 800; }
window .battery-mode-card.active .battery-mode-icon { color: #fff; background: #e52b45; }
window .battery-mode-title { font-size: 14px; font-weight: 800; }
window .battery-mode-limit { color: #ff5268; font-size: 20px; font-weight: 900; }
window .battery-mode-card.active .battery-mode-limit { color: #fff; }
window .battery-mode-description { color: #9aa2b1; font-size: 11px; }
window .battery-mode-caption { color: #68707d; font-size: 10px; font-weight: 700; letter-spacing: .5px; }
window .profile-name { font-size: 15px; font-weight: 800; }
window .profile-desc { color: #9299a7; font-size: 11px; }
window button.accent-button { background-color: #e52b45; background-image: none; color: #ffffff; font-weight: 800; border: 0; border-radius: 8px; padding: 9px 18px; box-shadow: none; }
window button.accent-button:hover { background-color: #fa3c56; background-image: none; box-shadow: none; }
window scale.ac-slider trough highlight { background-color: #e52b45; background-image: none; }
window scale.ac-slider trough highlight:disabled { background-color: #4a4f5a; background-image: none; }
window scale.ac-slider slider { background-color: #f4f5f8; background-image: none; border: 2px solid #e52b45; }
window .status-dot { color: #66dc9a; font-size: 13px; }
window .status-dot.off { color: #c9584f; font-size: 13px; }
window .footer { color: #69717f; font-size: 10px; }
window separator { background: #262b35; }
window .info-icon { opacity: 0.92; }
window .info-key { color: #7d8492; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }
window .info-val { color: #f4f5f8; font-size: 13px; font-weight: 700; }
window .opt-key { color: #9aa2b1; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }
window .swatch { border-radius: 8px; border: 1px solid #303641; }
window .lighting-description { color: #9299a7; font-size: 12px; }
window .lighting-layout { min-width: 520px; }
window .lighting-effects-panel { min-height: 360px; padding: 20px; border-radius: 5px; background: #101114; border-color: #292b31; }
window .lighting-section-header { min-height: 42px; margin-bottom: 2px; }
window .lighting-section-icon { min-width: 36px; min-height: 36px; padding: 7px; color: #ff5369; background: rgba(229,43,69,.10); border-radius: 4px; }
window .lighting-section-title { color: #f3f4f7; font-size: 15px; font-weight: 750; }
window .lighting-section-description { color: #8f98a7; font-size: 11px; }
window grid.lighting-effects-grid { margin-top: 4px; }
window button.lighting-effect-button { min-width: 74px; min-height: 94px; padding: 8px 5px; color: #b9bdc5; background: transparent; border: 1px solid transparent; border-radius: 4px; box-shadow: none; }
window button.lighting-effect-button:hover { color: #fff; background: rgba(255,255,255,.045); border-color: #353840; box-shadow: none; }
window button.lighting-effect-button:checked { color: #fff; background: rgba(229,43,69,.10); border-color: rgba(229,43,69,.65); box-shadow: inset 0 -2px #f32942; }
window .lighting-effect-icon { color: #aeb2bb; }
window button.lighting-effect-button:checked .lighting-effect-icon { color: #ff334f; }
window .lighting-effect-label { min-height: 26px; color: inherit; font-size: 10px; font-weight: 650; }
window .lighting-settings { min-width: 270px; padding: 18px; border-radius: 5px; background: #101114; border-color: #292b31; }
window .lighting-settings-heading { color: #e2e4e9; font-size: 11px; font-weight: 800; letter-spacing: 1.2px; }
window .lighting-selected-effect { color: #f4f5f8; font-size: 16px; font-weight: 750; }
window .lighting-description { color: #9299a7; font-size: 11px; }
window .lighting-control-heading { color: #b8bdc6; font-size: 10px; font-weight: 750; letter-spacing: .8px; }
window .lighting-brightness-value { color: #c5cad3; font-size: 11px; font-weight: 650; }
window .lighting-status { min-height: 14px; color: #8791a0; font-size: 10px; }
window .lighting-color-row { min-height: 40px; padding: 3px 0; }
window .lighting-color-label { min-width: 66px; color: #9da5b2; font-size: 9px; font-weight: 700; letter-spacing: .7px; }
window button.lighting-color-swatch { min-width: 29px; min-height: 29px; padding: 3px; border-radius: 999px; background: transparent; border: 1px solid transparent; box-shadow: none; }
window button.lighting-color-swatch:hover { background: #252a34; border-color: #5b6371; box-shadow: none; }
window button.lighting-color-swatch.selected { background: rgba(229,43,69,.14); border-color: #ff4059; box-shadow: none; }
window .lighting-color-picker-overlay { min-width: 38px; min-height: 38px; }
window button.color-picker-button { min-width: 36px; min-height: 36px; padding: 0; border-radius: 999px; }
window .lighting-color-picker-pin { padding: 3px; color: #fff; background: rgba(16,17,20,.9); border: 1px solid rgba(255,255,255,.7); border-radius: 999px; }
window scale.lighting-slider { min-height: 25px; }
window scale.lighting-slider trough { min-height: 4px; background: #373a40; border-radius: 0; }
window scale.lighting-slider trough highlight { background: #f32942; border-radius: 0; }
window scale.lighting-slider slider { min-width: 13px; min-height: 13px; background: #e5e7eb; border: 1px solid #ff334f; border-radius: 2px; }
window box.lighting-settings > separator { background: #36383d; }
window button.lighting-direction-button { min-width: 38px; min-height: 32px; color: #aeb5c0; background: #17191e; border: 1px solid #34373d; border-radius: 3px; box-shadow: none; }
window button.lighting-direction-button:checked { color: #fff; background: rgba(229,43,69,.2); border-color: #ef334c; }
window .color-palette { margin-top: 2px; margin-bottom: 8px; }
window button.color-swatch { min-width: 34px; min-height: 34px; padding: 3px; border-radius: 999px; background: transparent; border: 1px solid transparent; box-shadow: none; }
window button.color-swatch:hover { background: #252a34; border-color: #5b6371; box-shadow: none; }
window button.color-swatch.selected { background: rgba(229, 43, 69, 0.14); border-color: #ff4059; box-shadow: none; }
window .color-chip { min-width: 22px; min-height: 22px; }
window .color-picker-button { min-height: 36px; }
window headerbar { background: #050505; border-bottom: 1px solid #232833; box-shadow: none; }
window headerbar button { box-shadow: none; }
window .header-title { color: #f4f5f8; font-size: 15px; font-weight: 600; letter-spacing: 0; }
window .monitor-value { font-size: 15px; font-weight: 800; }
window .surface.monitor-card { padding: 20px 4px; background: transparent; border: 0; border-radius: 0; }
window .monitor-panel-title { color: #f4f5f8; font-size: 28px; font-weight: 400; }
window .monitor-header { color: #f4f5f8; font-size: 17px; font-weight: 700; }
window .device-hero { min-height: 205px; padding: 22px; border: 1px solid #303641; border-radius: 12px; background: #0b0e13; }
window .device-hero-copy { background: linear-gradient(90deg, rgba(9, 11, 16, .97), rgba(9, 11, 16, .82) 56%, rgba(9, 11, 16, .08)); padding: 18px; }
window .device-tabs { min-height: 38px; border-bottom: 1px solid #343b46; }
window button.device-tab { min-width: 150px; padding: 8px 14px; color: #929cab; background: transparent; border: 0; border-bottom: 2px solid transparent; border-radius: 0; box-shadow: none; font-size: 12px; font-weight: 700; }
window button.device-tab:hover { color: #f2f4f7; background: rgba(255,255,255,.035); box-shadow: none; }
window button.device-tab:checked { color: #ff5268; border-bottom-color: #ff334f; box-shadow: none; }
window .resource-toolbar { min-height: 38px; }
window .resource-recording { color: #ff5268; font-size: 10px; font-weight: 800; letter-spacing: 1px; }
window .resource-toolbar-label { color: #8892a0; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
window button.resource-record-button { min-width: 72px; min-height: 29px; padding: 3px 12px; color: #e4e8ed; background: #171c24; border: 1px solid #59616c; border-radius: 3px; box-shadow: none; font-size: 11px; }
window button.resource-record-button:hover { background: #222a34; box-shadow: none; }
window .resource-monitor-frame { min-height: 520px; background: #080b10; border: 1px solid #343b46; border-radius: 4px; }
window .resource-chart-wrap { min-width: 420px; padding: 8px; }
window .resource-chart { min-height: 500px; }
window .resource-metrics-panel { min-width: 164px; padding: 12px 7px; background: #10151c; border-left: 1px solid #343b46; }
window .resource-metrics-heading { color: #aeb7c4; font-size: 10px; font-weight: 800; letter-spacing: 1.3px; }
window .device-resource-detail { color: #86909f; font-size: 10px; }
window .resource-metric-row { min-height: 26px; border-bottom: 1px solid rgba(120, 128, 142, .12); }
window .resource-metric-dot { min-width: 12px; font-size: 9px; }
window .resource-metric-name { color: #c9d0d9; font-size: 10px; }
window .resource-metric-value { min-width: 58px; color: #f4f5f8; font-size: 10px; font-weight: 700; }
window .applications-panel { padding: 14px 16px; background: #10151c; border: 1px solid #343b46; border-radius: 4px; }
window .applications-heading { min-height: 38px; margin-bottom: 10px; }
window .applications-list-headings { min-height: 34px; padding: 0 12px; border-bottom: 1px solid #424a56; }
window .device-process-column { color: #8792a1; font-size: 9px; font-weight: 800; letter-spacing: .8px; }
window .application-row { min-height: 42px; padding: 2px 12px; border-bottom: 1px solid rgba(120, 128, 142, .10); border-radius: 3px; }
window .application-row:hover { background: rgba(80, 145, 230, .09); }
window .applications-row-alt { background: rgba(255,255,255,.018); }
window .device-process-name { color: #e5e8ed; font-size: 12px; }
window .application-icon { min-width: 22px; color: #aab5c4; }
window .device-process-value { color: #d4d9e1; font-size: 11px; font-variant-numeric: tabular-nums; }
window .dashboard-top { margin-bottom: 16px; }
window .dashboard-monitor { min-width: 400px; }
window .dashboard-monitor-grid { min-width: 400px; }
window .dashboard-metric { padding: 12px; border-radius: 9px; }
window .dashboard-metric .monitor-value { font-size: 14px; }
window .system-info-panel { padding: 16px 18px; }
window .system-info-row { min-height: 27px; }
window .system-info-row:not(:last-child) { border-bottom: 1px solid rgba(120, 128, 142, .12); }
window .system-info-row .info-key { min-width: 150px; }
window .sidebar-brand { padding: 8px 5px 16px; }
window .sidebar-brand-name { font-size: 11px; font-weight: 800; letter-spacing: .7px; }
window .sidebar-brand-subtitle { color: #737b88; font-size: 9px; letter-spacing: 1.6px; }
window .sidebar { padding: 8px 4px; }
window .sidebar-brand { padding: 4px 2px 10px; }
window .sidebar-menu-button { min-width: 34px; min-height: 34px; padding: 4px; background: transparent; border: 0; box-shadow: none; }
window button.nav { min-height: 40px; margin: 1px 0; padding: 4px 3px; font-size: 13px; }
window button.nav:checked { background: linear-gradient(90deg, rgba(229,43,69,.24), rgba(229,43,69,.06)); border-color: transparent; border-left: 3px solid #e52b45; }
window .ac-dashboard { padding: 8px 10px 12px; }
window .dashboard-toolbar { min-height: 48px; }
window .dashboard-brand-image { min-width: 105px; min-height: 32px; }
window .dashboard-system-strip { min-height: 100px; padding: 12px 10px; background: linear-gradient(100deg, #050505, #000000); border: 1px solid #303741; border-radius: 4px; }
window .dashboard-system-heading { min-height: 30px; color: #f1f3f6; font-size: __FONT_SIZE_DASHBOARD_HEADING__px; font-weight: 700; }
window .dashboard-system-info-item { padding: 0 13px; }
window .dashboard-info-icon { color: #a7b2c3; }
window .dashboard-info-label { color: #929cab; font-size: __FONT_SIZE_DASHBOARD_CAPTION__px; font-weight: 800; letter-spacing: 1.5px; }
window .dashboard-info-value { color: #f1f3f6; font-size: __FONT_SIZE_DASHBOARD_INFO__px; font-weight: 650; }
window .dashboard-system-strip separator { margin: 2px 0; background: #303741; }
window .dashboard-module { background: repeating-linear-gradient(135deg, #000000, #000000 3px, #070707 3px, #070707 5px); border: 1px solid #394047; border-radius: 3px; padding: 10px; }
window .dashboard-module.dashboard-cpu-panel { border: 0; }
window .dashboard-module-title { min-height: 30px; padding: 4px 8px; color: #dce1e8; font-size: __FONT_SIZE_DASHBOARD_HEADING__px; font-weight: 700; background: repeating-linear-gradient(135deg, #030303, #030303 4px, #0a0a0a 4px, #0a0a0a 6px); border: 1px solid #48515a; }
window .dashboard-compact-module { padding: 7px 9px; }
window .dashboard-stat-row { min-height: 24px; }
window .dashboard-stat-name { color: #d7dce4; font-size: __FONT_SIZE_DASHBOARD_BODY__px; }
window .dashboard-stat-value { color: #fff; font-size: __FONT_SIZE_DASHBOARD_STAT__px; font-weight: 700; }
window .dashboard-resource-card { min-width: 0; padding: 2px 3px; }
window .dashboard-resource-row { min-width: 0; }
window .dashboard-resource-meter { min-width: 72px; min-height: 72px; }
window .dashboard-resource-card .dashboard-value-large { font-size: __FONT_SIZE_DASHBOARD_READING__px; }
window .dashboard-compact-module .dashboard-stat-row { min-height: 23px; }
window .dashboard-stat-meter { min-height: 9px; margin: 0 0 3px 0; }
window .dashboard-tiny { color: #8b949e; font-size: __FONT_SIZE_DASHBOARD_CAPTION__px; }
window .dashboard-quick-button { background: linear-gradient(#282b30, #101216); color: #f2f4f6; border: 1px solid #5b6065; border-radius: 2px; padding: 6px 10px; box-shadow: none; }
window .dashboard-mode-button { background: transparent; color: #ddd; border: 0; border-bottom: 2px solid #40464e; border-radius: 0; padding: 8px 4px; box-shadow: none; }
window .dashboard-mode-button.active { color: #ff5268; border-bottom-color: #ff334f; background: rgba(229,43,69,.1); }
window .dashboard-cpu-gauge { min-height: 260px; }
window .dashboard-gauge-value { font-size: __FONT_SIZE_DASHBOARD_TEMPERATURE__px; font-weight: 700; color: #f5f6f8; }
window .dashboard-gauge-label { color: #b7bdc7; font-size: __FONT_SIZE_DASHBOARD_SECONDARY__px; }
window .dashboard-profile-entry { min-height: 68px; margin: 4px; padding: 12px 14px; }
window .dashboard-profile-entry .profile-symbol { min-width: 28px; margin-right: 4px; padding: 0; background: transparent; border: 0; border-radius: 0; color: #ff5268; font-size: 20px; }
window .dashboard-profile-entry.active { background: rgba(229,43,69,.12); border-bottom: 2px solid #e52b45; }
window .dashboard-profile-row { margin-top: 8px; }
window button.dashboard-profile-name { min-height: 34px; padding: 5px 8px; color: #dce1e8; background: transparent; border: 0; border-bottom: 2px solid #3a4049; border-radius: 0; box-shadow: none; font-size: __FONT_SIZE_DASHBOARD_BODY__px; }
window button.dashboard-profile-name:hover { color: #fff; background: rgba(255,255,255,.05); }
window button.dashboard-profile-name.active { color: #ff5268; background: rgba(229,43,69,.10); border-bottom-color: #ff334f; }
window button.dashboard-action-button { min-height: 42px; padding: 7px 10px; background: #151a22; border: 1px solid #303742; border-radius: 4px; color: #e9edf3; box-shadow: none; }
window button.dashboard-action-button:hover { background: #202630; border-color: #596474; box-shadow: none; }
window .dashboard-action-label { color: #e9edf3; font-size: __FONT_SIZE_DASHBOARD_BODY__px; font-weight: 650; }
window .dashboard-battery-icon { min-height: 38px; }
window .dashboard-unsupported { color: #7d858f; font-size: __FONT_SIZE_DASHBOARD_SECONDARY__px; }
window .dashboard-value-large { font-size: __FONT_SIZE_DASHBOARD_READING__px; font-weight: 700; color: #f7f8fa; }
window button.mode-option { background: transparent; border: 0; border-bottom: 1px solid #34363b; border-radius: 0; padding: 12px 10px 16px; box-shadow: none; }
window button.mode-option:hover { background: #141417; box-shadow: none; }
window button.mode-option.active { background: linear-gradient(180deg, transparent, rgba(220, 26, 47, .13)); border-bottom: 3px solid #e52b45; }
window .mode-option .profile-badge { min-width: 36px; min-height: 36px; background: transparent; border: 0; }
window .mode-option .profile-symbol { font-size: 22px; }
window levelbar.ac-level trough { background: #232833; border: none; border-radius: 2px; padding: 0; }
window levelbar.ac-level block { min-height: 4px; border: none; border-radius: 2px; padding: 0; }
window levelbar.ac-level block.filled { background: linear-gradient(90deg, #8a63ff, #ff4059); }
window .battery-page { background: radial-gradient(ellipse at 82% 18%, rgba(16, 100, 103, .12), transparent 38%), #0a1012; }
window .battery-page .eyebrow { color: #69c7c3; }
window .battery-page .page-title { font-size: 27px; }
window .battery-page-copy { color: #a3b2b4; font-size: 13px; line-height: 1.45; }
window .battery-layout { margin-top: 6px; }
window .battery-columns { min-height: 470px; }
window .battery-mode-list { min-width: 360px; }
window .battery-section-title { color: #7f999b; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }
window button.battery-mode-card { min-height: 112px; padding: 14px 16px; background: linear-gradient(120deg, #11191c, #101619); border: 1px solid #29383b; border-radius: 11px; color: #f0f5f5; box-shadow: none; }
window button.battery-mode-card:hover { background: #152124; border-color: #4a696b; box-shadow: none; }
window button.battery-mode-card.active { background: linear-gradient(105deg, rgba(35, 112, 112, .24), rgba(17, 31, 34, .95)); border-color: #55aaa7; box-shadow: inset 3px 0 #5cc7c2; }
window button.battery-mode-card.battery-limit-100.active { border-color: #c9a85d; box-shadow: inset 3px 0 #e6be5a; }
window button.battery-mode-card.battery-limit-60.active { border-color: #68c27b; box-shadow: inset 3px 0 #65d37d; }
window .battery-mode-radio { min-width: 20px; min-height: 20px; color: #607275; font-size: 19px; }
window .battery-mode-card.active .battery-mode-radio { color: #74d5d0; }
window button.battery-mode-card.battery-limit-100.active .battery-mode-radio { color: #f0cb6c; }
window button.battery-mode-card.battery-limit-60.active .battery-mode-radio { color: #72d287; }
window .battery-mode-title { color: #eff4f4; font-size: 14px; font-weight: 750; }
window .battery-mode-limit { color: #82bfc0; font-size: 15px; font-weight: 800; }
window .battery-limit-100 .battery-mode-limit { color: #e6be5a; }
window .battery-limit-60 .battery-mode-limit { color: #72d287; }
window .battery-mode-description { color: #a2b0b2; font-size: 11px; }
window .battery-mode-caption { color: #71aaa8; font-size: 10px; font-weight: 700; letter-spacing: .35px; }
window .battery-preview-panel { min-width: 320px; min-height: 530px; padding: 10px 16px; background: transparent; border: 0; border-radius: 0; }
window .battery-preview-heading { color: #7f999b; font-size: 10px; font-weight: 800; letter-spacing: 1.6px; }
window .battery-preview-badge { color: #73c6c1; background: rgba(62, 153, 149, .12); border: 1px solid rgba(99, 181, 177, .28); border-radius: 999px; padding: 4px 9px; font-size: 9px; font-weight: 750; }
window .battery-visual { min-width: 320px; min-height: 440px; }
window .battery-visual-value { font-size: 38px; font-weight: 850; color: #f4f7f7; text-shadow: 0 2px 14px rgba(0, 0, 0, .65); }
window .battery-visual-label { color: #d2dede; font-size: 14px; font-weight: 750; }
window .battery-visual-hint { color: #7f9698; font-size: 10px; }
window .battery-mini-stat { min-width: 115px; padding: 10px 12px; background: rgba(4, 12, 14, .45); border-color: #26393b; border-radius: 9px; }
window .battery-mini-stat .surface-title { color: #7f999b; font-size: 9px; }
window .battery-mini-stat .surface-value { color: #e9f1f1; font-size: 17px; }
window .battery-mini-stat .subtle { font-size: 9px; }
window .battery-live-footer { padding: 12px 14px 14px; background: linear-gradient(100deg, rgba(15, 29, 31, .94), rgba(12, 19, 22, .94)); border: 1px solid rgba(72, 121, 121, .25); border-radius: 10px; }
window .battery-live-header { min-height: 22px; }
window .battery-live-grid { margin-top: 8px; }
window .battery-live-item { min-width: 100px; padding: 8px 13px; background: rgba(4, 11, 13, .38); border: 1px solid rgba(96, 132, 133, .13); border-radius: 7px; }
window .battery-live-key { color: #7f999b; font-size: 9px; font-weight: 800; letter-spacing: 1.1px; }
window .battery-live-value { color: #e1ebeb; font-size: 12px; font-weight: 700; }
window .battery-live-indicator { color: #66d0a3; font-size: 10px; font-weight: 750; }
window button.battery-apply-button { min-height: 44px; padding: 10px 18px; background: linear-gradient(100deg, #167a7a, #1a9692); color: white; border: 1px solid #31aaa5; border-radius: 9px; font-size: 13px; font-weight: 800; box-shadow: 0 5px 20px rgba(15, 119, 116, .18); }
window button.battery-apply-button:hover { background: linear-gradient(100deg, #1b8c8a, #20aaa5); }
window button.battery-secondary-button { min-height: 42px; background: transparent; color: #9ab3b4; border: 1px solid #304649; border-radius: 9px; box-shadow: none; }
window button.battery-secondary-button:hover { background: #152124; color: #e5eeee; border-color: #527476; box-shadow: none; }
window .battery-feedback { color: #83c3bf; font-size: 10px; }
"""

CSS = CSS.replace(b"__FONT_FAMILY__", FONT_FAMILY.encode("ascii"))
for _role, _size in FONT_SIZES.items():
    _placeholder = f"__FONT_SIZE_{_role.upper()}__".encode("ascii")
    CSS = CSS.replace(_placeholder, str(_size).encode("ascii"))
