const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = 3000;
const DATA_DIR = path.join(__dirname, "..");

// ============ 日志工具 ============

function timestamp() {
  const now = new Date();
  const y = now.getFullYear();
  const mo = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  const h = String(now.getHours()).padStart(2, "0");
  const mi = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  return `[${y}-${mo}-${d} ${h}:${mi}:${s}]`;
}

// ---- 请求日志中间件 ----
app.use(function (req, res, next) {
  const start = Date.now();
  const clientIp = req.headers["x-forwarded-for"] || req.socket.remoteAddress || "-";
  console.log(`${timestamp()} --> ${req.method} ${req.originalUrl}  [${clientIp}]`);

  // 记录响应完成
  const origEnd = res.end;
  res.end = function () {
    const duration = Date.now() - start;
    console.log(`${timestamp()} <-- ${req.method} ${req.originalUrl}  ${res.statusCode}  (${duration}ms)`);
    origEnd.apply(res, arguments);
  };

  next();
});

// ============ 日期工具 ============

function resolveDate(dp) {
  const now = new Date();
  if (dp === "today" || dp === undefined || dp === null || dp === "")
    return formatDate(now);
  if (dp === "yesterday") {
    const y = new Date(now); y.setDate(y.getDate() - 1);
    return formatDate(y);
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(dp)) return dp;
  throw new Error("无效日期: " + dp + "，支持 today | yesterday | YYYY-MM-DD");
}

function formatDate(d) {
  return d.getFullYear() + "-" +
    String(d.getMonth() + 1).padStart(2, "0") + "-" +
    String(d.getDate()).padStart(2, "0");
}

// ============ 读取日报 ============

function readReport(targetDate) {
  const jsonFile = path.join(DATA_DIR, "Agent日报-" + targetDate + ".json");
  if (fs.existsSync(jsonFile)) {
    const data = JSON.parse(fs.readFileSync(jsonFile, "utf-8"));
    return {
      date: data.meta.date,
      total_fetched: data.meta.total_fetched,
      total_selected: data.meta.total_selected,
      sections: data.sections,
    };
  }
  return null;
}

function getReport(targetDate) {
  let date = targetDate;
  for (let i = 0; i < 30; i++) {
    const report = readReport(date);
    if (report) {
      return {
        ...report,
        match: date === targetDate ? "exact" : "nearest",
        requestedDate: targetDate,
      };
    }
    const d = new Date(date); d.setDate(d.getDate() - 1);
    date = formatDate(d);
  }
  throw new Error("未找到 " + targetDate + " 及之前 30 天内的日报");
}

function listAvailableDates() {
  const files = fs.readdirSync(DATA_DIR)
    .filter(function (f) {
      return /^Agent日报-(\d{4}-\d{2}-\d{2})\.json$/.test(f);
    })
    .map(function (f) {
      const m = f.match(/^Agent日报-(\d{4}-\d{2}-\d{2})\.json$/);
      return m[1];
    })
    .sort(function (a, b) { return b.localeCompare(a); });
  return files;
}

function listReports() {
  const files = fs.readdirSync(DATA_DIR)
    .filter(function (f) {
      return /^Agent日报-(\d{4}-\d{2}-\d{2})\.json$/.test(f);
    })
    .map(function (f) {
      const m = f.match(/^Agent日报-(\d{4}-\d{2}-\d{2})\.json$/);
      const filePath = path.join(DATA_DIR, f);
      const stat = fs.statSync(filePath);
      return { filename: f, date: m[1], size: stat.size };
    })
    .sort(function (a, b) { return b.date.localeCompare(a.date); });
}

// ============ 路由 ============

app.get("/", function (_req, res) {
  res.json({
    service: "xiaofan-local-api",
    version: "1.0",
    status: "ok",
    dataDir: DATA_DIR,
    usage: {
      latest: "GET /latest?date=today|yesterday|2026-08-06",
      list: "GET /list",
      dates: "GET /dates",
      report: "GET /report/2026-08-06",
    },
  });
});

app.get("/latest", function (req, res) {
  try {
    const d = resolveDate(req.query.date);
    res.json({ success: true, data: getReport(d) });
  } catch (err) {
    res.status(404).json({ success: false, error: err.message });
  }
});

app.get("/list", function (_req, res) {
  try {
    const files = listReports();
    res.json({ success: true, total: files.length, data: files });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get("/dates", function (_req, res) {
  try {
    const dates = listAvailableDates();
    res.json({ success: true, total: dates.length, data: dates });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get("/report/:date", function (req, res) {
  try {
    const d = resolveDate(req.params.date);
    res.json({ success: true, data: getReport(d) });
  } catch (err) {
    res.status(404).json({ success: false, error: err.message });
  }
});

// ============ 启动 ============

console.log("=".repeat(50));
console.log("xiaofan-local-api v1.0");
console.log("数据目录: " + DATA_DIR);
console.log("=".repeat(50));

app.listen(PORT, "0.0.0.0", function () {
  console.log("服务已启动: http://0.0.0.0:" + PORT);
  console.log("  GET /latest?date=today");
  console.log("  GET /latest?date=yesterday");
  console.log("  GET /latest?date=2026-08-06");
  console.log("  GET /list");
  console.log("  GET /dates");
  console.log("  GET /report/2026-08-06");
});
