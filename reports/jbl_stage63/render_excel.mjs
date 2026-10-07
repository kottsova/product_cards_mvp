import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/jbl_stage63';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/export.xlsx`));
const checks=await wb.inspect({kind:'table',range:"'Готовность JBL'!A1:G12",include:'values,formulas',tableMaxRows:12,tableMaxCols:7,maxChars:8000});
await fs.writeFile(`${root}/artifact_excel_inspect.json`,checks.ndjson);
for(const [name,range,filename] of [['Готовность JBL','A1:C12','excel_readiness'],['Готовность JBL','E1:G12','excel_identity'],['Характеристики-кандидаты JBL','A1:E22','excel_variant_candidates'],['headphones','A1:E5','excel_tune_rows']]){
 const result=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/${filename}.png`,new Uint8Array(await result.arrayBuffer()));
}
console.log('Read-only Excel inspection and 4 renders complete');

