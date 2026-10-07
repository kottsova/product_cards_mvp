import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/lenovo_stage60';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/export.xlsx`));
const checks=await wb.inspect({kind:'table',range:"'Готовность Lenovo'!A1:E11",include:'values,formulas',tableMaxRows:11,tableMaxCols:5,maxChars:3000});
await fs.writeFile(`${root}/artifact_excel_inspect.json`,checks.ndjson);
for(const [name,range,filename] of [['Готовность Lenovo','A1:E11','excel_readiness'],['Конфигурации-кандидаты','A1:G6','excel_candidates'],['laptop','A1:O7','excel_laptops']]){
 const result=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/${filename}.png`,new Uint8Array(await result.arrayBuffer()));
}
console.log('Read-only Excel artifact inspection and 3 renders complete');
