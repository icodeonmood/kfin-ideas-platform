import "server-only";

import QRCode from "qrcode";

/**
 * A QR code as one SVG path (one 1×1 square per dark module), for the launch screen (DEC-046). Built on the
 * server from our own APP_BASE_URL, so no markup is injected and nothing is fetched by the browser.
 */
export function qrPath(text: string): { size: number; d: string } {
  const qr = QRCode.create(text, { errorCorrectionLevel: "M" });
  const { size, data } = qr.modules;
  const parts: string[] = [];
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      if (data[row * size + col]) parts.push(`M${col} ${row}h1v1h-1z`);
    }
  }
  return { size, d: parts.join("") };
}
