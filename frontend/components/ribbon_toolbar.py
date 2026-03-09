from __future__ import annotations


def premium_theme_css() -> str:
    return """
:root{
  --bg:#0F0F0F;
  --surface:#1A1A1A;
  --accent:#FF6600;
  --accent2:#00CCFF;
  --text:#E0E0E0;
  --muted:#888888;
  --error:#FF3333;
  --ok:#00FF00;
}

.gradio-container,.dark,.app{
  background:var(--bg) !important;
  color:var(--text) !important;
}

.premium-card{
  background:var(--surface) !important;
  border:1px solid #262626 !important;
  border-radius:8px !important;
  box-shadow:0 4px 12px rgba(0,0,0,0.6) !important;
}

.premium-card .prose, .premium-card label, .premium-card span, .premium-card p, .premium-card div{
  color:var(--text);
  font-size:14px;
}

.muted{color:var(--muted)!important;font-size:12px!important;}
.hdr{font-size:16px!important;font-weight:700!important;color:#fff!important;}

#top-ribbon{
  position:sticky; top:0; z-index:999;
  height:48px; background:var(--surface);
  border-bottom:1px solid #2A2A2A;
  box-shadow:0 4px 12px rgba(0,0,0,0.6);
}

#top-ribbon .wrap{
  height:48px; padding:8px 12px; display:grid;
  grid-template-columns:22% 56% 22%; align-items:center; gap:8px;
}

#top-ribbon .brand{
  display:flex; align-items:center; gap:8px; min-width:0;
}

#top-ribbon .logo{
  width:32px; height:32px; border-radius:6px;
  background:linear-gradient(145deg,#FF6600,#D54E00);
  box-shadow:inset 0 0 0 1px rgba(255,255,255,0.15);
}

#top-ribbon .title{
  font-size:18px; font-weight:700; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}

#top-ribbon .mid{
  display:flex; align-items:center; justify-content:center; gap:8px; flex-wrap:nowrap;
}

#top-ribbon .right{
  justify-self:end; text-align:right; font-size:12px; color:var(--text); white-space:nowrap;
}

.status-dot{
  display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:middle;
}
.status-dot.ok{background:var(--ok); box-shadow:0 0 0 2px rgba(0,255,0,0.18);}
.status-dot.bad{background:var(--error); box-shadow:0 0 0 2px rgba(255,51,51,0.18);}

.premium-btn button{
  background:#232323 !important;
  border:1px solid #333 !important;
  color:var(--text) !important;
  min-height:32px !important;
  font-size:12px !important;
  box-shadow:0 4px 12px rgba(0,0,0,0.6) !important;
}

.premium-btn button:hover{
  filter:brightness(1.08);
  border:2px solid var(--accent) !important;
}

.premium-btn button:disabled{
  opacity:0.35 !important;
  cursor:not-allowed !important;
}

.btn-accent button{background:var(--accent)!important;color:#111!important;font-weight:700!important;}
.btn-cyan button{background:var(--accent2)!important;color:#101010!important;font-weight:700!important;}
.btn-danger button{background:#FF3333!important;color:#fff!important;font-weight:700!important;}
.btn-connect-ok button{background:#00FF00!important;color:#101010!important;font-weight:700!important;}

#workspace-row{gap:12px!important;}
#left-sidebar{min-width:280px;max-width:280px;}
#right-gauges{min-width:320px;max-width:320px;overflow-y:auto;max-height:calc(100vh - 260px);}
#center-main{min-height:520px;}

.hover-panel{
  transition:all 0.15s ease;
}
.hover-panel:hover{
  filter:brightness(1.08);
  border:2px solid var(--accent)!important;
}

#loading-overlay{
  position:fixed; inset:0; background:rgba(0,0,0,0.45);
  display:none; align-items:center; justify-content:center; z-index:2000;
}
#loading-overlay.visible{display:flex;}
.loader-wrap{
  background:#111; border:1px solid #2c2c2c; border-radius:10px; padding:16px 24px; text-align:center;
  box-shadow:0 4px 12px rgba(0,0,0,0.6);
}
.loader{
  width:24px; height:24px; border-radius:50%;
  border:3px solid rgba(255,102,0,0.25);
  border-top:3px solid #FF6600;
  margin:0 auto 8px auto; animation:spin 0.9s linear infinite;
}
@keyframes spin{to{transform:rotate(360deg)}}
.loader-text{font-size:12px;color:#E0E0E0}

#bottom-strip{
  margin-top:12px;
}
#bottom-strip .strip-head{
  display:flex; align-items:center; justify-content:space-between; gap:8px;
}
#bottom-strip .strip-body{
  max-height:180px; overflow:hidden; transition:max-height 0.25s ease;
}
#bottom-strip.collapsed .strip-body{max-height:0;}

/* TunerStudio Dialog Styles */
#dialog-overlay-container {
  background: #E0DFE3 !important; /* Classic Windows 95/98 gray */
  color: #000 !important;
  border: 1px solid #999 !important;
  box-shadow: 1px 1px 0px #FFF inset, -1px -1px 0px #888 inset, 2px 2px 5px rgba(0,0,0,0.4) !important;
  border-radius: 0 !important;
  padding: 8px !important;
  font-family: 'Tahoma', 'Segoe UI', sans-serif !important;
}

#dialog-overlay-container h3, .ts-fieldset h3 {
  font-size: 12px !important;
  color: #000080 !important; /* Classic navy blue header */
  margin-bottom: 4px !important;
  font-weight: normal !important;
}

.ts-fieldset {
  border: 1px solid #A0A0A0 !important;
  box-shadow: 1px 1px 0px #FFF !important;
  padding: 8px !important;
  margin-bottom: 8px !important;
  background: transparent !important;
}
.ts-fieldset > .label {
  display:none !important;
}

.ts-label {
  font-size: 11px !important;
  color: #000 !important;
}

.ts-input input, .ts-input select {
  background: #FFF !important;
  color: #000 !important;
  border: 1px solid #7A7A7A !important;
  border-radius: 0 !important;
  font-size: 11px !important;
  padding: 2px 4px !important;
  text-align: right !important;
  box-shadow: inset 1px 1px 2px rgba(0,0,0,0.1) !important;
}

.ts-bg-dark {
  background: #000 !important;
  border: 2px inset #555 !important;
}

.ts-red-banner p {
  background: #B22222 !important;
  color: #FFF !important;
  padding: 4px 8px !important;
  font-weight: bold !important;
  text-align: center !important;
  margin: 4px 0 !important;
}

.ts-blue-banner p {
  background: #4682B4 !important;
  color: #FFF !important;
  padding: 4px 8px !important;
  font-weight: bold !important;
  text-align: center !important;
  margin: 4px 0 !important;
}

/* Flex row fix for labels and inputs */
.ts-row {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  margin-bottom: 2px !important;
  gap: 8px !important;
}
.ts-row > * {
  flex: 1 !important;
}

.hidden-input {
  display: none !important;
}
"""



def loading_spinner_html() -> str:
    return """
<div id="loading-overlay">
  <div class="loader-wrap">
    <div class="loader"></div>
    <div class="loader-text">Communicating with ECU...</div>
  </div>
</div>
"""
