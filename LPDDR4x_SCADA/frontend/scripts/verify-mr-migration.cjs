// 验证 product.ts MR 契约与迁移（node + esbuild，无需测试框架）
// 契约（2026-09-01 定稿）：mr = {ch1, ch2: MrRow[]} 按通道分组，行名 MR5_2..MR8_2（_2 为固件键固定后缀）
// 迁移：①{ch1,ch2} 旧档保值；②{rank1,rank2} 中间版（2026-08-31 晚）→ 双通道同值（优先 _2 行）；
//       ③缺/非法 → 默认空值四行
const { execSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const src = path.resolve(__dirname, '../src/types/product.ts')
const out = path.resolve(__dirname, 'product_test.cjs')
execSync(`npx esbuild ${JSON.stringify(src)} --bundle --platform=node --format=cjs --outfile=${JSON.stringify(out)}`,
         { cwd: path.resolve(__dirname, '..'), stdio: 'inherit' })

const m = require(out)

// 1) 新默认结构：ch1/ch2 各四行 MR5_2..MR8_2，值空
const def = m.defaultProfiles()['LPDDR4x-16Gb']
const names = def.mr.ch1.map(r => r.name).join(',')
console.log('ch1 rows:', names, '| enabled checked:', def.mr.ch1.every(r => r.checked))
if (names !== 'MR5_2,MR6_2,MR7_2,MR8_2') throw new Error('ch1 行名错误')
if (def.mr.ch2.length !== 4) throw new Error('ch2 行数错误')

// 2) 中间版迁移：{rank1,rank2} → 双通道同值（优先 rank2 的 _2 行，回退 rank1 的 _1 行）
const mid = m.normalizeProfile({
  name: 'MID', rankEnabled: true, pl1Enabled: true, pl2Enabled: true,
  rankCapacityGb: [1, 1], channels: { ch1: true, ch2: true },
  mr: {
    rank1: { enabled: true, rows: [
      { name: 'MR5_1', value: '0x11', checked: true },
      { name: 'MR6_1', value: '0x66', checked: true }] },
    rank2: { enabled: true, rows: [
      { name: 'MR5_2', value: '0x1A', checked: true }] },
  },
  params: [], pl2: { testMode: '全映射读写测试', ascEnabled: true, ascOrder: '升序', patterns: {} },
})
const midCh1 = mid.mr.ch1
const mr5 = midCh1.find(r => r.name === 'MR5_2')
const mr6 = midCh1.find(r => r.name === 'MR6_2')
if (mr5.value !== '0x1A') throw new Error('MR5 应取 rank2 的 _2 行值')
if (mr6.value !== '0x66') throw new Error('MR6 应回退 rank1 的 _1 行值')
if (mid.mr.ch2.find(r => r.name === 'MR5_2').value !== '0x1A') throw new Error('双通道应同值')
console.log('中间版(rank1/rank2)迁移 OK: MR5=rank2值, MR6=rank1回退值, 双通道同值')

// 3) JSON 导入路径
const imp = m.parseProfileJson(JSON.stringify({ name: 'IMP' }))
if (!Array.isArray(imp.mr.ch1) || !Array.isArray(imp.mr.ch2)) throw new Error('导入档案 mr 结构错误')
console.log('parseProfileJson OK')
fs.unlinkSync(out)
console.log('ALL PASS')
