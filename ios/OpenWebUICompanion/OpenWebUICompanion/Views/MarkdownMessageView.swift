import SwiftUI

/// A compact Markdown renderer for streamed Open WebUI replies. It uses native
/// AttributedString support for inline Markdown and gives tables/code blocks a
/// readable mobile layout instead of showing their raw source.
struct MarkdownMessageView: View {
    let markdown: String

    private var blocks: [MarkdownBlock] { MarkdownParser.parse(markdown) }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
                blockView(block)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .textSelection(.enabled)
    }

    @ViewBuilder
    private func blockView(_ block: MarkdownBlock) -> some View {
        switch block {
        case let .heading(level, value):
            MarkdownInlineText(value)
                .font(level == 1 ? .title3.bold() : level == 2 ? .headline : .subheadline.weight(.semibold))
                .foregroundStyle(TechTheme.primaryText)
                .padding(.top, level == 1 ? 6 : 2)
        case let .paragraph(value):
            MarkdownInlineText(value)
                .font(.body)
                .foregroundStyle(TechTheme.primaryText)
                .fixedSize(horizontal: false, vertical: true)
        case let .bullet(value):
            HStack(alignment: .top, spacing: 8) {
                Text("•").foregroundStyle(TechTheme.teal)
                MarkdownInlineText(value)
                    .font(.body)
                    .foregroundStyle(TechTheme.primaryText)
            }
        case let .code(language, value):
            VStack(alignment: .leading, spacing: 8) {
                if let language, !language.isEmpty {
                    Text(language.uppercased())
                        .font(.caption2.weight(.bold))
                        .tracking(0.8)
                        .foregroundStyle(TechTheme.cyan)
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    Text(value)
                        .font(.system(.footnote, design: .monospaced))
                        .foregroundStyle(TechTheme.primaryText)
                        .padding(12)
                }
            }
            .background(TechTheme.codeSurface, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(TechTheme.line, lineWidth: 1)
            }
        case let .table(headers, rows):
            MarkdownTable(headers: headers, rows: rows)
        }
    }
}

private struct MarkdownInlineText: View {
    let value: String

    init(_ value: String) { self.value = value }

    var body: some View {
        if let attributed = try? AttributedString(
            markdown: value,
            options: .init(interpretedSyntax: .full, failurePolicy: .returnPartiallyParsedIfPossible)
        ) {
            Text(attributed)
        } else {
            Text(value)
        }
    }
}

private struct MarkdownTable: View {
    let headers: [String]
    let rows: [[String]]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            Grid(alignment: .leading, horizontalSpacing: 0, verticalSpacing: 0) {
                GridRow {
                    ForEach(Array(headers.enumerated()), id: \.offset) { _, header in
                        MarkdownInlineText(header)
                            .font(.caption.weight(.bold))
                            .foregroundStyle(TechTheme.cyan)
                            .frame(minWidth: 124, maxWidth: 220, alignment: .leading)
                            .padding(10)
                            .background(TechTheme.cyan.opacity(0.12))
                    }
                }
                ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                    GridRow {
                        ForEach(Array(headers.indices), id: \.self) { index in
                            MarkdownInlineText(index < row.count ? row[index] : "")
                                .font(.caption)
                                .foregroundStyle(TechTheme.primaryText)
                                .frame(minWidth: 124, maxWidth: 220, alignment: .leading)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(10)
                                .background(TechTheme.panel.opacity(0.64))
                        }
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(TechTheme.line, lineWidth: 1)
            }
        }
        .accessibilityLabel("Markdown 表格，\(headers.count) 欄，\(rows.count) 列")
    }
}

private enum MarkdownBlock {
    case heading(Int, String)
    case paragraph(String)
    case bullet(String)
    case code(String?, String)
    case table([String], [[String]])
}

private enum MarkdownParser {
    static func parse(_ source: String) -> [MarkdownBlock] {
        let lines = source.components(separatedBy: .newlines)
        var blocks: [MarkdownBlock] = []
        var index = 0

        while index < lines.count {
            let line = lines[index]
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty { index += 1; continue }

            if trimmed.hasPrefix("```") {
                let language = String(trimmed.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                var content: [String] = []
                index += 1
                while index < lines.count, !lines[index].trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                    content.append(lines[index])
                    index += 1
                }
                if index < lines.count { index += 1 }
                blocks.append(.code(language.isEmpty ? nil : language, content.joined(separator: "\n")))
                continue
            }

            if let heading = heading(from: trimmed) {
                blocks.append(.heading(heading.level, heading.value))
                index += 1
                continue
            }

            if index + 1 < lines.count, isTableDivider(lines[index + 1]), trimmed.contains("|") {
                let headers = tableCells(line)
                var rows: [[String]] = []
                index += 2
                while index < lines.count, lines[index].contains("|"), !lines[index].trimmingCharacters(in: .whitespaces).isEmpty {
                    rows.append(tableCells(lines[index]))
                    index += 1
                }
                if !headers.isEmpty { blocks.append(.table(headers, rows)) }
                continue
            }

            if let bullet = bulletValue(from: trimmed) {
                blocks.append(.bullet(bullet))
                index += 1
                continue
            }

            var paragraph: [String] = [trimmed]
            index += 1
            while index < lines.count {
                let next = lines[index].trimmingCharacters(in: .whitespaces)
                if next.isEmpty || next.hasPrefix("```") || heading(from: next) != nil || bulletValue(from: next) != nil ||
                    (index + 1 < lines.count && isTableDivider(lines[index + 1]) && next.contains("|")) {
                    break
                }
                paragraph.append(next)
                index += 1
            }
            blocks.append(.paragraph(paragraph.joined(separator: "\n")))
        }
        return blocks.isEmpty ? [.paragraph(source)] : blocks
    }

    private static func heading(from value: String) -> (level: Int, value: String)? {
        let hashes = value.prefix { $0 == "#" }
        guard !hashes.isEmpty, hashes.count <= 6 else { return nil }
        let remainder = value.dropFirst(hashes.count)
        guard remainder.first == " " else { return nil }
        return (hashes.count, String(remainder.dropFirst()).trimmingCharacters(in: .whitespaces))
    }

    private static func bulletValue(from value: String) -> String? {
        if value.hasPrefix("- ") || value.hasPrefix("* ") || value.hasPrefix("+ ") {
            return String(value.dropFirst(2))
        }
        let parts = value.split(separator: " ", maxSplits: 1, omittingEmptySubsequences: true)
        guard parts.count == 2,
              let marker = parts.first,
              marker.last == ".",
              marker.dropLast().allSatisfy(\.isNumber) else { return nil }
        return String(parts[1])
    }

    private static func isTableDivider(_ value: String) -> Bool {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        guard trimmed.contains("|"), trimmed.contains("-") else { return false }
        let permitted = CharacterSet(charactersIn: "|-: \t")
        return trimmed.unicodeScalars.allSatisfy { permitted.contains($0) }
    }

    private static func tableCells(_ value: String) -> [String] {
        var cells = value.split(separator: "|", omittingEmptySubsequences: false).map {
            String($0).trimmingCharacters(in: .whitespaces)
        }
        if cells.first?.isEmpty == true { cells.removeFirst() }
        if cells.last?.isEmpty == true { cells.removeLast() }
        return cells
    }
}
