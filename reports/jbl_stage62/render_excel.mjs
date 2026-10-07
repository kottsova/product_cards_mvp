import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/jbl_stage62';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/export.xlsx`));
const checks=await wb.inspect({kind:'table',range:"'Готовность JBL'!A1:E12",include:'values,formulas',tableMaxRows:12,tableMaxCols:5,maxChars:8000});
await fs.writeFile(`${root}/artifact_excel_inspect.json`,checks.ndjson);
for(const [name,range,filename] of [['Готовность JBL','A1:E12','excel_readiness'],['headphones','U1:X5','excel_battery'],['tws','O1:V2','excel_tws_components'],['Документы-кандидаты JBL','A1:F8','excel_documents']]){
 const result=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/${filename}.png`,new Uint8Array(await result.arrayBuffer()));
}
console.log('Read-only Excel inspection and 4 renders complete');
