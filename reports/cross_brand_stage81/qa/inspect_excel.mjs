import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
import fs from 'node:fs/promises';
const path=process.argv[2];
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path));
const inventory=await book.inspect({kind:'sheet',include:'id,name',maxChars:8000});
await fs.writeFile(path+'.artifact_sheets.json',JSON.stringify(inventory,null,2));
console.log(book.help('workbook.render',{include:'index,examples,notes',maxChars:2200}).ndjson);
console.log('Imported native workbook',path);
