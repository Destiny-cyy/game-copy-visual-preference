/* 运行级验证（通用版）：真实执行 HTML 里的画图代码，确认每张图都能画出来
   用法：node verify_html_charts.js <HTML路径> [期望图数]
   原理：Node + ECharts SSR（服务端渲染 SVG），mock DOM 后跑业务画图脚本，
        断言每张图 renderToSVGString() 产出含 <rect>/<path> 的图形。
   为什么需要：只查「占位符/结构/语法」会漏掉 CDN 加载失败导致的整片空白。 */
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const echarts = require(path.join(__dirname, '..', 'assets', 'echarts.min.js'));

const htmlPath = process.argv[2];
const expectN = parseInt(process.argv[3] || '0', 10);
if (!htmlPath) { console.error('用法: node verify_html_charts.js <HTML路径> [期望图数]'); process.exit(2); }
const html = fs.readFileSync(htmlPath, 'utf-8');

// 1) 静态：页面渲染依赖的 CDN 外链必须清零（内容超链接 <a href> 不算）
const extDeps = [...html.matchAll(/<(?:script|link|img)[^>]+(?:src|href)="https?:\/\/[^"]*"/g)];
console.log('渲染依赖外链数（应=0）=', extDeps.length);
if (extDeps.length) { extDeps.slice(0, 5).forEach(m => console.log('  ', m[0])); }

// 2) 运行级：真实执行画图代码
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const biz = scripts[scripts.length - 1];
const charts = [];
const sandbox = {
  window: { addEventListener: function () {} },
  document: { getElementById: id => ({ id, innerHTML: '' }), addEventListener: function () {} },
  navigator: { userAgent: 'node-verify' },
  echarts: { init: function () {
    const inst = echarts.init(null, null, { renderer: 'svg', ssr: true, width: 1120, height: 460 });
    charts.push(inst); return inst;
  } }
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
try { vm.runInContext(biz, sandbox, { timeout: 15000 }); }
catch (e) { console.error('业务画图脚本执行失败：', e.message); process.exit(1); }

console.log('draw 调用次数 =', charts.length);
let ok = extDeps.length === 0;
charts.forEach((inst, i) => {
  const svg = inst.renderToSVGString();
  const drawn = svg.length > 500 && svg.includes('<svg') && (svg.includes('<rect') || svg.includes('<path'));
  console.log(`图 ${i + 1}: SVG 长度=${svg.length}, 已绘制=${drawn ? 'OK' : 'FAIL'}`);
  if (!drawn) ok = false;
});
if (expectN && charts.length !== expectN) { console.log(`图数不符：期望 ${expectN}，实际 ${charts.length}`); ok = false; }
console.log(ok ? '=== 验证通过：零外链 + 所有图真实可渲染 ===' : '=== 验证失败 ===');
process.exit(ok ? 0 : 1);
