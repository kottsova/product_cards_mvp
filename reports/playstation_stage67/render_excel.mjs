import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='reports/playstation_stage67';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/export.xlsx`));
const result=await wb.inspect({kind:'table',range:"'Готовность PlayStation'!A1:H11",include:'values,formulas',tableMaxRows:11,tableMaxCols:8,maxChars:10000});
await fs.writeFile(`${root}/artifact_excel_inspect.json`,result.ndjson);
for(const [sheetName,range,name] of [['Готовность PlayStation','B1:K11','readiness'],['Конфигурация PlayStation','A1:C8','configuration'],['Кандидаты PlayStation','A1:C8','candidates'],['Документы PlayStation','A1:G8','documents'],['Связь SKU и CFI','A1:G8','sku_cfi']]){
  const blob=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(`${root}/excel_${name}.png`,new Uint8Array(await blob.arrayBuffer()));
}
console.log('Read-only native Excel inspection and 5 renders complete');

process.exit(0);
