import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const reporterDir = path.dirname(fileURLToPath(import.meta.url));

function normalizeError(result) {
  if (!result?.error) {
    return "";
  }
  return String(result.error.message || result.error.value || result.error).trim();
}

class DefectReporter {
  onBegin(config, suite) {
    this.config = config;
    this.totalTests = suite.allTests().length;
    this.failures = [];
    this.startedAt = new Date().toISOString();
  }

  onTestEnd(test, result) {
    if (result.status !== "failed") {
      return;
    }

    this.failures.push({
      title: test.title,
      file: test.location.file,
      line: test.location.line,
      project: test.parent.project()?.name || "default",
      durationMs: result.duration,
      error: normalizeError(result),
      attachments: result.attachments.map((attachment) => ({
        name: attachment.name,
        path: attachment.path || null,
        contentType: attachment.contentType || null,
      })),
    });
  }

  onEnd(result) {
    const outDir = path.resolve(reporterDir, "../artifacts/defects");
    fs.mkdirSync(outDir, { recursive: true });

    const payload = {
      startedAt: this.startedAt,
      finishedAt: new Date().toISOString(),
      status: result.status,
      totalTests: this.totalTests,
      failedTests: this.failures.length,
      failures: this.failures,
      metadata: this.config.metadata,
    };

    fs.writeFileSync(
      path.join(outDir, "defect-report.json"),
      JSON.stringify(payload, null, 2),
    );

    const lines = [
      "# Defect Report",
      "",
      `- Status: ${result.status}`,
      `- Started: ${this.startedAt}`,
      `- Finished: ${payload.finishedAt}`,
      `- Total tests: ${this.totalTests}`,
      `- Failed tests: ${this.failures.length}`,
      "",
    ];

    if (this.failures.length === 0) {
      lines.push("No defects were captured in this run.");
    } else {
      for (const failure of this.failures) {
        lines.push(`## ${failure.title}`);
        lines.push(`- File: ${failure.file}:${failure.line}`);
        lines.push(`- Project: ${failure.project}`);
        lines.push(`- Duration: ${failure.durationMs}ms`);
        if (failure.error) {
          lines.push("- Error:");
          lines.push("```text");
          lines.push(failure.error);
          lines.push("```");
        }
        if (failure.attachments.length > 0) {
          lines.push("- Attachments:");
          for (const attachment of failure.attachments) {
            lines.push(
              `  - ${attachment.name}: ${attachment.path || attachment.contentType || "inline"}`,
            );
          }
        }
        lines.push("");
      }
    }

    fs.writeFileSync(path.join(outDir, "defect-report.md"), `${lines.join("\n")}\n`);
  }
}

export default DefectReporter;
