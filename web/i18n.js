// UI strings in 中文 / English. Pick with ?lang=zh|en, the 中/EN button, or the browser language; remembered in localStorage.
// Every user-facing string lives here (same keys as Unity's L10n.cs) — never put literals in app.js / index.html.
export const STR = {
  zh: {
    title: 'DoodLive · 涂色天使 AR', tagline: '给天使涂上颜色，用手机一扫——她会活过来',
    scan: '开始扫描涂色纸', demo: '没有纸？看演示', print: '打印涂色纸', battle: '⚔️ 大卫 vs 歌利亚（战斗剧场）',
    shoot: '拍下识别', rescan: '重新扫描', modeShow: '展示模式', modePaper: '纸上模式',
    linesOn: '线条：显示', linesOff: '线条：隐藏', pinyin: '拼音', abc: 'ABC', xr: '放到桌上（AR）', exitXR: '退出 AR',
    openingCam: '正在打开相机…', camFail: '打不开相机：{e}。可以先看演示',
    fit: '把整张涂色纸放进框里，四个黑方块对准四个角', found: '找到了！拿稳别动…', recognised: '识别成功',
    tap: '点一下天使，听她吹响号角', tapXR: '点天使听号角 · 点“放到桌上”让她站进真实空间',
    xrFind: '慢慢移动手机找到桌面或地面，出现金色光圈后点一下屏幕', xrNoPlane: '还没找到平面，先慢慢移动手机，等金色光圈出现再点',
    xrPlaced: '点天使听号角 · 点别处的地面可以挪动她', xrExit: '已退出 AR · 点“重新扫描”可以再拍一张',
    needMarkers: '先让四个黑方块进入画面', xrFail: '进入 AR 失败：{e}',
    notrack: 'AR 还没开始追踪：对着明亮、有花纹的桌面或地面，左右慢慢平移手机', nosurface: '在找平面…对准桌面或地面，稍微移动一下', ok: '找到了！点一下屏幕，把天使放在金色光圈上',
    hello: '哇！我活过来啦！谢谢你给我涂上这么漂亮的颜色！',
    line0: '听！天堂的号角为你吹响！', line1: '你画得真好看，我好喜欢这些颜色！', line2: '愿你今天平安、快乐！', line3: '再给我画一件新衣服吧！',
  },
  en: {
    title: 'DoodLive · Colour-in Angel AR', tagline: 'Colour the angel, scan it with your phone — and she comes to life',
    scan: 'Scan my colouring sheet', demo: 'No sheet? Watch the demo', print: 'Print a colouring sheet', battle: '⚔️ David vs Goliath (battle theatre)',
    shoot: 'Capture', rescan: 'Scan again', modeShow: 'Showcase', modePaper: 'On the page',
    linesOn: 'Lines: shown', linesOff: 'Lines: hidden', pinyin: 'Pinyin', abc: 'ABC', xr: 'Place on the table (AR)', exitXR: 'Exit AR',
    openingCam: 'Opening the camera…', camFail: 'Camera unavailable: {e}. Try the demo',
    fit: 'Fit the whole sheet in the frame, the four black squares in the corners', found: 'Found it! Hold still…', recognised: 'Recognised',
    tap: 'Tap the angel to hear her trumpet', tapXR: 'Tap her for the trumpet · "Place on the table" puts her in your room',
    xrFind: 'Move the phone slowly over a table or floor; tap when the gold ring appears', xrNoPlane: 'No surface yet — move the phone slowly until the gold ring appears',
    xrPlaced: 'Tap her for the trumpet · tap elsewhere on the floor to move her', xrExit: 'Left AR · "Scan again" to take another shot',
    needMarkers: 'Get the four black squares into view first', xrFail: 'Could not start AR: {e}',
    notrack: 'AR is not tracking yet: aim at a bright, textured table or floor and pan slowly', nosurface: 'Looking for a surface… aim at the table or floor and move a little', ok: 'Found one! Tap the screen to place the angel on the gold ring',
    hello: 'Wow! I\'m alive! Thank you for colouring me so beautifully!',
    line0: 'Listen! The trumpet of heaven sounds for you!', line1: 'Your drawing is lovely, I adore these colours!', line2: 'May your day be safe and happy!', line3: 'Draw me a new dress next time!',
  },
};
const saved = (() => { try { return localStorage.getItem('lang'); } catch { return null; } })();
const fromUrl = new URLSearchParams(location.search).get('lang');
export let lang = ['zh', 'en'].includes(fromUrl) ? fromUrl : saved || (navigator.language?.toLowerCase().startsWith('zh') ? 'zh' : 'en');
export const t = (key, vars = {}) => (STR[lang][key] ?? STR.zh[key] ?? key).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
export const other = key => (STR[lang === 'zh' ? 'en' : 'zh'][key] ?? '');
export function setLang(l) { lang = l; try { localStorage.setItem('lang', l); } catch {} apply(); }
export function apply() {
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.title = t('title');
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll('[data-lang-toggle]')) el.textContent = lang === 'zh' ? 'EN' : '中';
  document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
}
