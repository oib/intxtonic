#!/usr/bin/env node
import { checkWithOllama } from './ollama.js';

async function main() {
  try {
    const arg = process.argv[2];
    if (!arg) {
      console.error('Usage: node dev/ollama_cli.mjs <json_sequence_array>');
      process.exit(2);
    }
    let seq;
    try {
      seq = JSON.parse(arg);
      if (!Array.isArray(seq)) throw new Error('not an array');
    } catch (e) {
      console.error('Invalid sequence JSON:', e.message);
      process.exit(2);
    }
    const out = await checkWithOllama(seq);
    process.stdout.write(String(out).trim() + '\n');
  } catch (e) {
    console.error('ollama_cli failed:', e);
    process.exit(1);
  }
}

main();
