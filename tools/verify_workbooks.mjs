import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const files = process.argv.slice(2);
for (const file of files) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
  const sheet = workbook.worksheets.getItemAt(0);
  const used = sheet.getUsedRange(true);
  const inspection = await workbook.inspect({
    kind: "table",
    sheetId: sheet.name,
    range: used.address,
    include: "values,formulas",
    tableMaxRows: 5,
    tableMaxCols: 8,
    maxChars: 5000,
  });
  console.log(`FILE ${file}`);
  console.log(inspection.ndjson);
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 50 },
    summary: "formula errors",
  });
  console.log(errors.ndjson);
  const preview = await workbook.render({ sheetName: sheet.name, range: used.address, scale: 1, format: "png" });
  const previewPath = file.replace(/\.xlsx$/i, ".png");
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  console.log(`PREVIEW ${previewPath}`);
}
