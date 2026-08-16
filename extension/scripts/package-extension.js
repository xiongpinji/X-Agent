const fs = require('node:fs')
const path = require('node:path')
const archiver = require('archiver')

const ROOT = path.resolve(__dirname, '..')
const PACKAGE_FILES = [
  'manifest.json',
  'popup.html',
  'popup.css',
  'extension-api.js',
  'popup.js',
  'images/icon-16.png',
  'images/icon-48.png',
  'images/icon-128.png',
]
const FIXED_DATE = new Date('1980-01-01T00:00:00.000Z')

async function createPackage(outputPath = path.join(ROOT, 'dist', 'x-agent-extension.zip')) {
  return new Promise((resolve, reject) => {
    for (const name of PACKAGE_FILES) {
      if (!fs.statSync(path.join(ROOT, name)).isFile()) throw new Error(`Missing package input: ${name}`)
    }
    fs.mkdirSync(path.dirname(outputPath), { recursive: true })
    const output = fs.createWriteStream(outputPath)
    const archive = archiver('zip', { zlib: { level: 9 } })
    output.on('close', () => resolve(outputPath))
    output.on('error', reject)
    archive.on('error', reject)
    archive.pipe(output)
    for (const name of PACKAGE_FILES) {
      archive.append(fs.readFileSync(path.join(ROOT, name)), {
        name,
        date: FIXED_DATE,
        mode: 0o100644,
      })
    }
    archive.finalize()
  })
}

function listZipEntries(buffer) {
  let eocd = -1
  for (let offset = buffer.length - 22; offset >= Math.max(0, buffer.length - 65_557); offset -= 1) {
    if (buffer.readUInt32LE(offset) === 0x06054b50) {
      eocd = offset
      break
    }
  }
  if (eocd < 0) throw new Error('Invalid ZIP: end record missing')
  const count = buffer.readUInt16LE(eocd + 10)
  let offset = buffer.readUInt32LE(eocd + 16)
  const entries = []
  for (let index = 0; index < count; index += 1) {
    if (buffer.readUInt32LE(offset) !== 0x02014b50) throw new Error('Invalid ZIP: central directory missing')
    const nameLength = buffer.readUInt16LE(offset + 28)
    const extraLength = buffer.readUInt16LE(offset + 30)
    const commentLength = buffer.readUInt16LE(offset + 32)
    entries.push(buffer.subarray(offset + 46, offset + 46 + nameLength).toString('utf8'))
    offset += 46 + nameLength + extraLength + commentLength
  }
  return entries
}

if (require.main === module) {
  createPackage()
    .then((output) => process.stdout.write(`Created ${output}\n`))
    .catch((error) => {
      process.stderr.write(`${error.message}\n`)
      process.exitCode = 1
    })
}

module.exports = { PACKAGE_FILES, createPackage, listZipEntries }
