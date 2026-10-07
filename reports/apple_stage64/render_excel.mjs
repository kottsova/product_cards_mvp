import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/apple_stage64';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/export.xlsx`));
const checks=await wb.inspect({kind:'table',range:"'Готовность Apple'!A1:H12",include:'values,formulas',tableMaxRows:12,tableMaxCols:8,maxChars:8000});
await fs.writeFile(`${root}/artifact_excel_inspect.json`,checks.ndjson);
for(const [name,range,filename] of [['Готовность Apple','B1:C12','excel_readiness'],['Готовность Apple','D1:G12','excel_identity'],['Варианты-кандидаты Apple','B1:E12','excel_candidates'],['laptops','A1:F4','excel_laptops']]){
 const result=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/${filename}.png`,new Uint8Array(await result.arrayBuffer()));
}
console.log('Read-only Excel inspection and 4 renders complete');

