import Foundation
import SQLite3
import Testing
@testable import vibe_hud

@MainActor
@Suite("OpenCode SQLite conversations")
struct OpenCodeConversationTests {
    @Test("Reads messages, reasoning, every completed tool, errors, and usage from SQLite")
    func readsConversation() async throws {
        let fixture = try makeFixture()
        defer { sqlite3_close(fixture.connection); try? FileManager.default.removeItem(at: fixture.root) }
        let parser = ConversationParser()
        let messages = await parser.parseFullConversation(
            sessionId: "session", cwd: "/tmp/project", transcriptPath: fixture.url.path
        )
        #expect(messages.map(\.id) == ["user", "assistant"])
        #expect(messages.map(\.textContent) == ["Inspect the project", "Done"])
        #expect(messages.last?.content.contains(.thinking("Inspecting")) == true)
        let completed = await parser.completedToolIds(for: "session")
        #expect(completed == ["call-read", "call-edit"])
        let results = await parser.toolResults(for: "session")
        #expect(results["call-read"]?.stdout == "file contents")
        #expect(results["call-edit"]?.isError == true)
        #expect(results["call-edit"]?.stderr == "Permission denied")
        let info = await parser.parse(sessionId: "session", cwd: "/tmp/project", transcriptPath: fixture.url.path)
        #expect(info.summary == "SQLite session")
        #expect(info.firstUserMessage == "Inspect the project")
        #expect(info.lastMessage == "Done")
        #expect(info.lastToolName == "Edit")
        #expect(info.usage.inputTokens == 20)
        #expect(info.usage.outputTokens == 5)
        #expect(info.usage.cacheReadTokens == 3)
    }

    @Test("Refreshes existing streamed messages and titles while writes remain in the WAL")
    func refreshesWALChanges() async throws {
        let fixture = try makeFixture()
        defer { sqlite3_close(fixture.connection); try? FileManager.default.removeItem(at: fixture.root) }
        let parser = ConversationParser()
        _ = await parser.parseFullConversation(sessionId: "session", cwd: "/tmp/project", transcriptPath: fixture.url.path)
        let before = try fixture.url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate
        try execute("UPDATE part SET data = '{\"type\":\"text\",\"text\":\"Updated response\"}' WHERE id = 'text';", in: fixture.connection)
        try execute("UPDATE session SET title = 'Updated title' WHERE id = 'session';", in: fixture.connection)
        let after = try fixture.url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate
        #expect(before == after)
        let update = await parser.parseIncremental(
            sessionId: "session", cwd: "/tmp/project", transcriptPath: fixture.url.path
        )
        #expect(update.newMessages.isEmpty)
        #expect(update.hasStateChanges)
        #expect(update.allMessages.last?.textContent == "Updated response")
        let info = await parser.parse(sessionId: "session", cwd: "/tmp/project", transcriptPath: fixture.url.path)
        #expect(info.summary == "Updated title")
        #expect(info.lastMessage == "Updated response")
    }

    @Test("Keeps sessions isolated and never creates a missing database")
    func isolatesSessions() throws {
        let fixture = try makeFixture()
        defer { sqlite3_close(fixture.connection); try? FileManager.default.removeItem(at: fixture.root) }
        #expect(try OpenCodeSessionDatabase.snapshot(sessionId: "' OR 1=1 --", at: fixture.url.path) == nil)
        let other = try OpenCodeSessionDatabase.snapshot(sessionId: "other", at: fixture.url.path)
        #expect(other?.title == "Other session")
        #expect(other?.messages.isEmpty == true)
        let missing = fixture.root.appendingPathComponent("missing.db")
        #expect(throws: (any Error).self) {
            try OpenCodeSessionDatabase.snapshot(sessionId: "session", at: missing.path)
        }
        #expect(!FileManager.default.fileExists(atPath: missing.path))
    }

    @Test("Updates visible conversation text without duplicating messages or losing tool errors")
    func refreshesSessionStore() async throws {
        let fixture = try makeFixture()
        defer { sqlite3_close(fixture.connection); try? FileManager.default.removeItem(at: fixture.root) }
        let store = SessionStore(initialSessions: [SessionState(
            sessionId: "session", cwd: "/tmp/project", source: .opencode,
            transcriptPath: fixture.url.path, phase: .processing
        )])
        await store.process(.loadHistory(sessionId: "session", cwd: "/tmp/project"))
        try execute("UPDATE part SET data = '{\"type\":\"text\",\"text\":\"Updated response\"}' WHERE id = 'text';", in: fixture.connection)
        let parser = ConversationParser()
        let messages = await parser.parseFullConversation(sessionId: "session", cwd: "/tmp/project", transcriptPath: fixture.url.path)
        await store.process(.fileUpdated(FileUpdatePayload(
            sessionId: "session", cwd: "/tmp/project", transcriptPath: fixture.url.path,
            messages: messages, isIncremental: false,
            completedToolIds: await parser.completedToolIds(for: "session"),
            toolResults: await parser.toolResults(for: "session"),
            structuredResults: await parser.structuredResults(for: "session")
        )))
        let updated = try #require(await store.session(for: "session"))
        #expect(updated.chatItems.filter { $0.type == .user("Inspect the project") }.count == 1)
        #expect(updated.chatItems.contains { $0.type == .assistant("Updated response") })
        #expect(!updated.chatItems.contains { $0.type == .assistant("Done") })
        let failed = updated.chatItems.first { $0.id == "call-edit" }
        if case .toolCall(let tool) = failed?.type {
            #expect(tool.status == .error)
        } else {
            Issue.record("Missing failed tool")
        }
    }

    private func makeFixture() throws -> (root: URL, url: URL, connection: OpaquePointer) {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let url = root.appendingPathComponent("custom-database")
        var connection: OpaquePointer?
        guard sqlite3_open(url.path, &connection) == SQLITE_OK, let connection else {
            throw FixtureError.database
        }
        try execute("""
        PRAGMA journal_mode=WAL;
        PRAGMA wal_autocheckpoint=0;
        CREATE TABLE session (id TEXT PRIMARY KEY, title TEXT);
        CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);
        CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
        INSERT INTO session VALUES ('session', 'SQLite session'), ('other', 'Other session');
        INSERT INTO message VALUES ('assistant', 'session', 2000, '{"role":"assistant","tokens":{"input":20,"output":5,"cache":{"read":3}}}');
        INSERT INTO message VALUES ('user', 'session', 1000, '{"role":"user"}');
        INSERT INTO part VALUES ('prompt', 'user', 'session', 1000, '{"type":"text","text":"Inspect the project"}');
        INSERT INTO part VALUES ('reasoning', 'assistant', 'session', 2000, '{"type":"reasoning","text":"Inspecting"}');
        INSERT INTO part VALUES ('text', 'assistant', 'session', 2001, '{"type":"text","text":"Done"}');
        INSERT INTO part VALUES ('tool1', 'assistant', 'session', 2002, '{"type":"tool","tool":"read","callID":"call-read","state":{"status":"completed","input":{"path":"file.swift"},"output":"file contents"}}');
        INSERT INTO part VALUES ('tool2', 'assistant', 'session', 2003, '{"type":"tool","tool":"edit","callID":"call-edit","state":{"status":"error","input":{},"error":"Permission denied"}}');
        PRAGMA wal_checkpoint(TRUNCATE);
        """, in: connection)
        return (root, url, connection)
    }

    private func execute(_ sql: String, in connection: OpaquePointer) throws {
        guard sqlite3_exec(connection, sql, nil, nil, nil) == SQLITE_OK else { throw FixtureError.database }
    }

    private enum FixtureError: Error { case database }
}
