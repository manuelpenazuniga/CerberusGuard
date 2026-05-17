const required = ["OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY"];

for (const key of required) {
  if (!process.env[key]) {
    console.log(`[warn] missing env ${key}`);
  }
}

console.log("test scaffold completed");
