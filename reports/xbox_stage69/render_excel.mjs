import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/xbox_stage69';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/export.xlsx`));
const result=await wb.inspect({kind:'table',range:"'Готовность Xbox'!A1:I11",include:'values,formulas',tableMaxRows:11,tableMaxCols:9,maxChars:10000});
await fs.writeFile(`${root}/artifact_excel_inspect.json`,result.ndjson);
for(const [sheetName,range,name] of [['Готовность Xbox','A1:I11','readiness'],['Конфигурация Xbox','A1:D12','configuration'],['Идентификаторы Xbox','A1:E10','identifiers'],['Кандидаты Xbox','A1:E8','candidates'],['Документы Xbox','A1:G8','documents'],['Связи Xbox','A1:I6','relations'],['Принятые факты Xbox','A1:G8','accepted']]){
 const blob=await wb.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/excel_${name}.png`,new Uint8Array(await blob.arrayBuffer()));
}
console.log('Read-only native Excel inspection and five renders complete');
process.exit(0);
