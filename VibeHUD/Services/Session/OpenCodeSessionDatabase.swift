import Foundation
import SQLite3

struct OpenCodeStoredMessage: Sendable {
    let id: String
    let createdAtMilliseconds: Int64
    let data: Data
    let parts: [Data]

    nonisolated init(id: String, createdAtMilliseconds: Int64, data: Data, parts: [Data]) {
        self.id = id
        self.createdAtMilliseconds = createdAtMilliseconds
        self.data = data
        self.parts = parts
    }
}

struct OpenCodeDatabaseSnapshot: Sendable {
    let title: String?
    let messages: [OpenCodeStoredMessage]

    nonisolated init(title: String?, messages: [OpenCodeStoredMessage]) {
        self.title = title
        self.messages = messages
    }
}

/// Reads a consistent snapshot without creating, migrating, or modifying OpenCode's database.
enum OpenCodeSessionDatabase {
    nonisolated static func isDatabase(at path: String) -> Bool {
        guard let handle = FileHandle(forReadingAtPath: path) else { return false }
        defer { try? handle.close() }
        return (try? handle.read(upToCount: 16)) == Data("SQLite format 3\0".utf8)
    }

    nonisolated static func snapshot(sessionId: String, at path: String) throws -> OpenCodeDatabaseSnapshot? {
        var connection: OpaquePointer?
        let result = sqlite3_open_v2(path, &connection, SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX, nil)
        guard result == SQLITE_OK, let connection else {
            sqlite3_close(connection)
            throw DatabaseError.operationFailed("Unable to open OpenCode session database")
        }
        defer { sqlite3_close(connection) }
        sqlite3_busy_timeout(connection, 250)
        try execute("BEGIN", in: connection)
        defer { sqlite3_exec(connection, "ROLLBACK", nil, nil, nil) }

        let session = try prepare("SELECT title FROM session WHERE id = ?", sessionId: sessionId, in: connection)
        defer { sqlite3_finalize(session) }
        let sessionResult = sqlite3_step(session)
        if sessionResult == SQLITE_DONE { return nil }
        guard sessionResult == SQLITE_ROW else { throw failure(in: connection) }
        let title = string(session, column: 0)

        let partQuery = try prepare(
            "SELECT message_id, data FROM part WHERE session_id = ? ORDER BY time_created, id",
            sessionId: sessionId, in: connection
        )
        defer { sqlite3_finalize(partQuery) }
        var parts: [String: [Data]] = [:]
        while true {
            let step = sqlite3_step(partQuery)
            if step == SQLITE_DONE { break }
            guard step == SQLITE_ROW else { throw failure(in: connection) }
            if let messageId = string(partQuery, column: 0), let json = string(partQuery, column: 1) {
                parts[messageId, default: []].append(Data(json.utf8))
            }
        }

        let messageQuery = try prepare(
            "SELECT id, time_created, data FROM message WHERE session_id = ? ORDER BY time_created, id",
            sessionId: sessionId, in: connection
        )
        defer { sqlite3_finalize(messageQuery) }
        var messages: [OpenCodeStoredMessage] = []
        while true {
            let step = sqlite3_step(messageQuery)
            if step == SQLITE_DONE { break }
            guard step == SQLITE_ROW else { throw failure(in: connection) }
            if let id = string(messageQuery, column: 0), let json = string(messageQuery, column: 2) {
                messages.append(OpenCodeStoredMessage(
                    id: id,
                    createdAtMilliseconds: sqlite3_column_int64(messageQuery, 1),
                    data: Data(json.utf8),
                    parts: parts[id] ?? []
                ))
            }
        }
        return OpenCodeDatabaseSnapshot(title: title, messages: messages)
    }

    nonisolated private static func prepare(
        _ query: String, sessionId: String, in connection: OpaquePointer
    ) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(connection, query, -1, &statement, nil) == SQLITE_OK, let statement else {
            throw failure(in: connection)
        }
        let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
        guard sqlite3_bind_text(statement, 1, sessionId, -1, transient) == SQLITE_OK else {
            sqlite3_finalize(statement)
            throw failure(in: connection)
        }
        return statement
    }

    nonisolated private static func execute(_ query: String, in connection: OpaquePointer) throws {
        guard sqlite3_exec(connection, query, nil, nil, nil) == SQLITE_OK else {
            throw failure(in: connection)
        }
    }

    nonisolated private static func string(_ statement: OpaquePointer, column: Int32) -> String? {
        sqlite3_column_text(statement, column).map { String(cString: $0) }
    }

    nonisolated private static func failure(in connection: OpaquePointer) -> DatabaseError {
        .operationFailed(String(cString: sqlite3_errmsg(connection)))
    }

    private enum DatabaseError: Error {
        case operationFailed(String)
    }
}
