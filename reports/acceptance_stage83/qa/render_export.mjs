import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/acceptance_stage83';
const qa=JSON.parse(await fs.readFile(`${root}/export_qa.json`,'utf8'));
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/Apple_Acceptance.xlsx`));
await fs.writeFile(`${root}/qa/workbook_inspection.json`,JSON.stringify(await book.inspect({kind:'sheet',include:'id,name',maxChars:5000}),null,2));
for(let i=0;i<qa.render_ranges.length;i++){
 const r=qa.render_ranges[i];
 const preview=await book.render({sheetName:r.sheet,range:r.range,scale:1,format:'png'});
 await fs.writeFile(`${root}/qa/export_sheet_${i}.png`,new Uint8Array(await preview.arrayBuffer()));
}
console.log(`Read-only import and render complete: ${qa.render_ranges.length} worksheets`);
