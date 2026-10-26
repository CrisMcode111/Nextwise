/** App-owned discovery adapter. Caller holds the bridge's existing nextwise.lock. */
import crypto from "node:crypto";
import { HMEM } from "../vendor/meterless/hmem/reference/src/index.ts";
const hash = (s: string) => crypto.createHash("sha256").update(s).digest("hex");
export function discoveryRecords(hmem: HMEM, request: any, directory: string) {
  const records = hmem.store.all().filter(r => r.source === "nextwise:discovery");
  const decoded = records.map(r => {
    const envelope = JSON.parse(r.content);
    if (hash(JSON.stringify(envelope.value)) !== envelope.sha256) throw new Error("Discovery integrity failure");
    return envelope.value;
  }).sort((a,b) => a.version-b.version);
  decoded.forEach((v,i) => { if(v.version !== i+1) throw new Error("Discovery history gap"); });
  const current = decoded.at(-1) ?? {version:0, baselines:{}, items:{}, runs:[], proposals:[]};
  if (request.operation === "discovery_read") return {discovery:current};
  if (request.discovery?.version !== current.version+1) throw new Error("Discovery version conflict");
  const value = request.discovery;
  const content = JSON.stringify({value, sha256:hash(JSON.stringify(value))});
  const record = hmem.add({content, type:"general", layer:"working", source:"nextwise:discovery",
    chatId:request.investigation_id, tags:["project:nextwise", "discovery:checkpoint"],
    provenance:{origin:"manual", learnedAt:Date.now(), label:"User-triggered discovery; untrusted public content"}});
  const disk = new HMEM({persistDir:directory, actor:"nextwise:discovery-readback"});
  if(disk.store.get(record.id)?.content !== content) throw new Error("Discovery persistence unconfirmed");
  return {discovery:value};
}
