import assert from "node:assert/strict"
import fs from "node:fs/promises"
import net from "node:net"
import os from "node:os"
import path from "node:path"

const repoRoot = path.resolve(import.meta.dirname, "..")
const pluginPath = path.join(repoRoot, "VibeHUD/Resources/vibe-hud.js")
const socketPath = path.join(os.tmpdir(), `vibe-hud-test-${process.pid}.sock`)

const source = (await fs.readFile(pluginPath, "utf8")).replace(
  'const SOCKET_PATH = "/tmp/vibe-hud.sock"',
  `const SOCKET_PATH = ${JSON.stringify(socketPath)}`,
)
const moduleURL = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
const pluginFactory = (await import(moduleURL)).default
const plugin = await pluginFactory()
const fixtureRoot = await fs.mkdtemp(path.join(os.tmpdir(), "vibe-hud-opencode-"))
const originalDataHome = process.env.XDG_DATA_HOME
const originalDatabase = process.env.OPENCODE_DB

const server = net.createServer()
await new Promise((resolve) => server.listen(socketPath, resolve))

async function captureEvent(input) {
  const received = new Promise((resolve) => {
    server.once("connection", (socket) => {
      let body = ""
      socket.on("data", (chunk) => { body += chunk.toString("utf8") })
      socket.on("end", () => resolve(JSON.parse(body)))
    })
  })
  await plugin.event(input)
  return received
}

try {
  process.env.XDG_DATA_HOME = fixtureRoot
  delete process.env.OPENCODE_DB
  const dataDir = path.join(fixtureRoot, "opencode")
  const legacySession = path.join(dataDir, "storage/session/project/session-1.json")
  await fs.mkdir(path.dirname(legacySession), { recursive: true })
  await fs.writeFile(legacySession, JSON.stringify({ id: "session-1" }))
  const created = () => captureEvent({
    event: { type: "session.created", properties: { info: { id: "session-1", directory: fixtureRoot } } },
  })
  assert.equal((await created()).transcript_path, legacySession)
  const database = path.join(dataDir, "opencode.db")
  await fs.writeFile(database, "SQLite format 3\0")
  assert.equal((await created()).transcript_path, database)
  const customDatabase = path.join(fixtureRoot, "custom.sqlite")
  await fs.writeFile(customDatabase, "SQLite format 3\0")
  process.env.OPENCODE_DB = customDatabase
  assert.equal((await created()).transcript_path, customDatabase)

  const busy = await captureEvent({
    event: {
      type: "session.status",
      properties: { sessionID: "session-1", status: { type: "busy" } },
    },
  })
  assert.equal(busy.event, "SessionStatus")
  assert.equal(busy.status, "processing")

  const idle = await captureEvent({
    event: {
      type: "session.status",
      properties: { sessionID: "session-1", status: { type: "idle" } },
    },
  })
  assert.equal(idle.event, "Stop")
  assert.equal(idle.status, "waiting_for_input")

  const permission = await captureEvent({
    event: {
      type: "permission.asked",
      properties: {
        id: "permission-1",
        sessionID: "session-1",
        permission: "bash",
        patterns: ["pwd"],
        metadata: { tool: "bash" },
      },
    },
  })

  assert.equal(permission.session_id, "session-1")
  assert.equal(permission.status, "waiting_for_approval")
  assert.equal(permission.tool, "Bash")
  assert.equal(permission.tool_use_id, "permission-1")
  assert.deepEqual(permission.tool_input.patterns, ["pwd"])

  const permissionResolved = await captureEvent({
    event: {
      type: "permission.replied",
      properties: { sessionID: "session-1" },
    },
  })
  assert.equal(permissionResolved.event, "PermissionResolved")
  assert.equal(permissionResolved.status, "processing")

  const question = await captureEvent({
    event: {
      type: "question.asked",
      properties: {
        sessionID: "session-1",
        questions: [{ question: "Continue?" }],
      },
    },
  })
  assert.equal(question.event, "QuestionPending")
  assert.equal(question.status, "waiting_for_input")
  assert.equal(question.message, "Continue?")

  const questionResolved = await captureEvent({
    event: {
      type: "question.rejected",
      properties: { sessionID: "session-1" },
    },
  })
  assert.equal(questionResolved.event, "QuestionResolved")
  assert.equal(questionResolved.status, "processing")

  const failure = await captureEvent({
    event: {
      type: "session.error",
      properties: {
        sessionID: "session-1",
        error: { name: "APIError", data: { message: "Rate limited" } },
      },
    },
  })

  assert.equal(failure.status, "failed")
  assert.equal(failure.message, "Rate limited")
} finally {
  if (originalDataHome === undefined) delete process.env.XDG_DATA_HOME
  else process.env.XDG_DATA_HOME = originalDataHome
  if (originalDatabase === undefined) delete process.env.OPENCODE_DB
  else process.env.OPENCODE_DB = originalDatabase
  await new Promise((resolve) => server.close(resolve))
  await fs.rm(socketPath, { force: true })
  await fs.rm(fixtureRoot, { recursive: true, force: true })
}
