import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
const identity={subject:"eng-a",roles:["engineer"],sites:["site-a"],verified:true};
afterEach(()=>vi.unstubAllGlobals());
describe("upload client",()=>{
  it("sends multipart without overriding its boundary and includes identity",async()=>{
    const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({document_id:"d"})}); vi.stubGlobal("fetch",fetchMock);
    await api.uploadDocument(new File(["%PDF-"],"manual.pdf",{type:"application/pdf"}),identity);
    const [,init]=fetchMock.mock.calls[0]; expect(init.body).toBeInstanceOf(FormData); expect(init.headers["Content-Type"]).toBeUndefined(); expect(init.headers["X-Dev-Subject"]).toBe("eng-a");
  });
});
