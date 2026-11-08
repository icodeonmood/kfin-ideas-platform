/**
 * Column encryption for drafts and submitted text waiting for a scan (§4.1 step 2, §4.2 failure handling).
 * AES-256-GCM. Layout: [0x01 version][12-byte IV][16-byte tag][ciphertext]. The row's ID is bound in as
 * associated data, so a ciphertext copied into another row fails to open. The key comes from
 * VAULT_ENCRYPTION_KEY (vault-held, 32+ characters outside dev). Python reads the same layout from B4.
 */
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";

import { isProductionLike } from "./config";

const VERSION = 0x01;

function key(): Buffer {
  const raw = process.env.VAULT_ENCRYPTION_KEY;
  if (!raw) throw new Error("VAULT_ENCRYPTION_KEY is not set");
  if (isProductionLike() && (raw.startsWith("change-me") || raw.length < 32)) {
    throw new Error("VAULT_ENCRYPTION_KEY is a placeholder or too short for this environment");
  }
  return createHash("sha256").update(raw, "utf8").digest();
}

export function encryptJson(value: unknown, context: string): Buffer {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key(), iv);
  cipher.setAAD(Buffer.from(context, "utf8"));
  const body = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
  return Buffer.concat([Buffer.from([VERSION]), iv, cipher.getAuthTag(), body]);
}

export function decryptJson<T>(blob: Buffer, context: string): T {
  if (blob.length < 29 || blob[0] !== VERSION) throw new Error("unknown ciphertext format");
  const decipher = createDecipheriv("aes-256-gcm", key(), blob.subarray(1, 13));
  decipher.setAAD(Buffer.from(context, "utf8"));
  decipher.setAuthTag(blob.subarray(13, 29));
  const plain = Buffer.concat([decipher.update(blob.subarray(29)), decipher.final()]);
  return JSON.parse(plain.toString("utf8")) as T;
}
