// Read-only artifact-tool QA of the application's native export.
import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='A:/work/dev/product_cards_mvp/reports/dreame_stage76';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/Dreame_Stage76.xlsx`));
for (const [sheetName,range,file] of [
 ['Dreame готовность','A1:J11','readiness'],
 ['Dreame конфигурация','A1:D14','input_configuration'],
 ['Роботы-пылесосы','A1:E6','robots']
]) {
 const b=await wb.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/qa/excel_${file}.png`,new Uint8Array(await b.arrayBuffer()));
 console.log(`Rendered ${sheetName}`);
}
