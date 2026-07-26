import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath =
  "../../rubic-check/Coursework Tracking (Public).xlsx";
const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const sheets = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 4000,
});
const sheet3 = await workbook.inspect({
  kind: "table",
  sheetId: "Sheet3",
  range: "A1:E63",
  include: "values,formulas",
  tableMaxRows: 63,
  tableMaxCols: 5,
  tableMaxCellChars: 240,
  maxChars: 30000,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "rubric formula error scan",
  maxChars: 4000,
});

console.log("SHEETS");
console.log(sheets.ndjson);
console.log("SHEET3");
console.log(sheet3.ndjson);
console.log("ERRORS");
console.log(errors.ndjson);
