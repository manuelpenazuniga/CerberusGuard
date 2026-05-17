use std::{fs, path::PathBuf};

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};

#[derive(Debug, Parser)]
#[command(name = "cerberus-policy")]
#[command(about = "Compile a unified CerberusGuard policy into LT/PP/CC configs")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    Compile {
        policy: PathBuf,
        #[arg(long)]
        out_dir: PathBuf,
    },
    Validate {
        policy: PathBuf,
    },
    ListPresets,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct UnifiedPolicy {
    version: String,
    policy_name: String,
    profile: String,
    agent_meta: AgentMeta,
    prompt_inspection: PromptInspection,
    budget: Budget,
    execution: Execution,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct AgentMeta {
    budget_caps: BudgetCaps,
    session_limits: SessionLimits,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct BudgetCaps {
    per_request_usd: f64,
    per_session_usd: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct SessionLimits {
    max_requests: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct PromptInspection {
    block: Vec<String>,
    require_review: Vec<String>,
    log_only: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct Budget {
    enforcement: String,
    loop_detection: LoopDetection,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct LoopDetection {
    enabled: bool,
    similarity_threshold: f64,
    consecutive_limit: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct Execution {
    default_profile: String,
    command_profiles: Vec<CommandProfile>,
    denied_paths: Vec<String>,
    env_scrub: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct CommandProfile {
    name: String,
    allow: Vec<String>,
    deny: Vec<String>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Compile { policy, out_dir } => compile_command(policy, out_dir),
        Commands::Validate { policy } => validate_command(policy),
        Commands::ListPresets => list_presets_command(),
    }
}

fn compile_command(policy_path: PathBuf, out_dir: PathBuf) -> Result<()> {
    let policy = read_policy(&policy_path)?;
    fs::create_dir_all(&out_dir).with_context(|| format!("create {}", out_dir.display()))?;

    let lt_cfg = compile_lobstertrap(&policy)?;
    let pp_cfg = compile_pennyprompt(&policy)?;
    let cc_cfg = compile_clawcrate(&policy)?;

    fs::write(out_dir.join("lobstertrap.yaml"), lt_cfg).context("write lobstertrap.yaml")?;
    fs::write(out_dir.join("pennyprompt.toml"), pp_cfg).context("write pennyprompt.toml")?;
    fs::write(out_dir.join("clawcrate.yaml"), cc_cfg).context("write clawcrate.yaml")?;
    Ok(())
}

fn validate_command(policy_path: PathBuf) -> Result<()> {
    let policy = read_policy(&policy_path)?;
    let yaml = serde_yaml::to_string(&policy)?;
    let reparsed: UnifiedPolicy = serde_yaml::from_str(&yaml)?;
    if policy != reparsed {
        anyhow::bail!("round-trip validation failed");
    }
    println!("valid: {}", policy_path.display());
    Ok(())
}

fn list_presets_command() -> Result<()> {
    let presets = ["policy/examples/healthcare-strict.yaml"];
    for preset in presets {
        println!("{preset}");
    }
    Ok(())
}

fn read_policy(path: &PathBuf) -> Result<UnifiedPolicy> {
    let raw = fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    let policy: UnifiedPolicy =
        serde_yaml::from_str(&raw).with_context(|| format!("parse {}", path.display()))?;
    Ok(policy)
}

fn compile_lobstertrap(policy: &UnifiedPolicy) -> Result<String> {
    #[derive(Serialize)]
    struct LtPolicy<'a> {
        version: &'a str,
        policy_name: &'a str,
        profile: &'a str,
        rules: LtRules<'a>,
    }
    #[derive(Serialize)]
    struct LtRules<'a> {
        block: &'a [String],
        require_review: &'a [String],
        log_only: &'a [String],
    }
    let cfg = LtPolicy {
        version: &policy.version,
        policy_name: &policy.policy_name,
        profile: &policy.profile,
        rules: LtRules {
            block: &policy.prompt_inspection.block,
            require_review: &policy.prompt_inspection.require_review,
            log_only: &policy.prompt_inspection.log_only,
        },
    };
    Ok(serde_yaml::to_string(&cfg)?)
}

fn compile_pennyprompt(policy: &UnifiedPolicy) -> Result<String> {
    #[derive(Serialize)]
    struct PpPolicy<'a> {
        policy_name: &'a str,
        profile: &'a str,
        budget: PpBudget<'a>,
    }
    #[derive(Serialize)]
    struct PpBudget<'a> {
        enforcement: &'a str,
        per_request_usd: f64,
        per_session_usd: f64,
        max_requests: u32,
        loop_detection: &'a LoopDetection,
    }
    let cfg = PpPolicy {
        policy_name: &policy.policy_name,
        profile: &policy.profile,
        budget: PpBudget {
            enforcement: &policy.budget.enforcement,
            per_request_usd: policy.agent_meta.budget_caps.per_request_usd,
            per_session_usd: policy.agent_meta.budget_caps.per_session_usd,
            max_requests: policy.agent_meta.session_limits.max_requests,
            loop_detection: &policy.budget.loop_detection,
        },
    };
    Ok(toml::to_string_pretty(&cfg)?)
}

fn compile_clawcrate(policy: &UnifiedPolicy) -> Result<String> {
    #[derive(Serialize)]
    struct CcPolicy<'a> {
        policy_name: &'a str,
        profile: &'a str,
        execution: &'a Execution,
    }
    let cfg = CcPolicy {
        policy_name: &policy.policy_name,
        profile: &policy.profile,
        execution: &policy.execution,
    };
    Ok(serde_yaml::to_string(&cfg)?)
}

#[cfg(test)]
mod tests {
    use super::{UnifiedPolicy, validate_command};
    use std::{fs, path::PathBuf};

    fn sample_policy() -> &'static str {
        r#"
version: "1.0"
policy_name: "healthcare-strict"
profile: "strict"
agent_meta:
  budget_caps:
    per_request_usd: 0.05
    per_session_usd: 1.5
  session_limits:
    max_requests: 50
prompt_inspection:
  block: ["credentials", "exfiltration"]
  require_review: ["pii_request"]
  log_only: ["code_snippet"]
budget:
  enforcement: "deny"
  loop_detection:
    enabled: true
    similarity_threshold: 0.9
    consecutive_limit: 4
execution:
  default_profile: "safe"
  command_profiles:
    - name: "safe"
      allow: ["echo", "ls"]
      deny: ["curl"]
  denied_paths: ["/etc/shadow", "~/.ssh"]
  env_scrub: ["AWS_SECRET_ACCESS_KEY"]
"#
    }

    #[test]
    fn round_trip_parse_serialize_parse() {
        let parsed: UnifiedPolicy = serde_yaml::from_str(sample_policy()).expect("parse policy");
        let serialized = serde_yaml::to_string(&parsed).expect("serialize policy");
        let reparsed: UnifiedPolicy = serde_yaml::from_str(&serialized).expect("reparse policy");
        assert_eq!(parsed, reparsed);
    }

    #[test]
    fn missing_field_returns_error() {
        let broken = r#"
version: "1.0"
policy_name: "broken"
"#;
        let path = PathBuf::from("/private/tmp/cerberus-policy-missing.yaml");
        fs::write(&path, broken).expect("write broken policy");
        let result = validate_command(path);
        assert!(result.is_err());
    }
}
