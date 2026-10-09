import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/razer_stage70';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/export.xlsx`));
const result=await wb.inspect({kind:'table',range:"'Готовность Razer'!A1:H11",include:'values,formulas',tableMaxRows:11,tableMaxCols:8,maxChars:10000});
await fs.writeFile(`${root}/artifact_excel_inspect.json`,result.ndjson);
for(const [sheetName,range,name] of [['Готовность Razer','A1:H11','readiness'],['Варианты Razer','A1:D10','variants'],['Кандидаты Razer','A1:E8','candidates']]){
 const blob=await wb.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/excel_${name}.png`,new Uint8Array(await blob.arrayBuffer()));
}
process.exit(0);
