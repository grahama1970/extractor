var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";
// https://vitejs.dev/config/
function detectProxyTarget() {
    return __awaiter(this, void 0, void 0, function () {
        var candidates, _i, candidates_1, base, r, _a;
        return __generator(this, function (_b) {
            switch (_b.label) {
                case 0:
                    if (process.env.VITE_API_PROXY)
                        return [2 /*return*/, process.env.VITE_API_PROXY];
                    candidates = [
                        'http://127.0.0.1:8000',
                        'http://localhost:8000',
                        'http://127.0.0.1:8001',
                        'http://localhost:8001',
                    ];
                    _i = 0, candidates_1 = candidates;
                    _b.label = 1;
                case 1:
                    if (!(_i < candidates_1.length)) return [3 /*break*/, 6];
                    base = candidates_1[_i];
                    _b.label = 2;
                case 2:
                    _b.trys.push([2, 4, , 5]);
                    return [4 /*yield*/, fetch(base + '/api/build', { method: 'GET', signal: AbortSignal.timeout(300) })];
                case 3:
                    r = _b.sent();
                    if (r.ok)
                        return [2 /*return*/, base];
                    return [3 /*break*/, 5];
                case 4:
                    _a = _b.sent();
                    return [3 /*break*/, 5];
                case 5:
                    _i++;
                    return [3 /*break*/, 1];
                case 6: return [2 /*return*/, 'http://localhost:8000'];
            }
        });
    });
}
export default defineConfig(function (_a) { return __awaiter(void 0, [_a], void 0, function (_b) {
    var _c, _d;
    var _e, _f, _g, _h, _j;
    var mode = _b.mode;
    return __generator(this, function (_k) {
        switch (_k.label) {
            case 0:
                _e = {};
                _f = {
                    host: "0.0.0.0",
                    port: 8080,
                    strictPort: true,
                    headers: mode === "development" ? {
                        "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                        "Surrogate-Control": "no-store",
                    } : undefined
                };
                _g = {};
                // Proxy API calls during dev to FastAPI backend (uvicorn on :8000)
                _c = "/api";
                _h = {};
                return [4 /*yield*/, detectProxyTarget()];
            case 1:
                // Proxy API calls during dev to FastAPI backend (uvicorn on :8000)
                _g[_c] = (_h.target = _k.sent(),
                    _h.changeOrigin = true,
                    _h);
                _d = "/ws";
                _j = {};
                return [4 /*yield*/, detectProxyTarget()];
            case 2: return [2 /*return*/, (_e.server = (_f.proxy = (_g[_d] = (_j.target = _k.sent(),
                    _j.changeOrigin = true,
                    _j.ws = true,
                    _j),
                    _g),
                    _f),
                    _e.preview = {
                        host: "0.0.0.0",
                        port: 8080,
                        strictPort: true,
                        headers: {
                            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
                            "Pragma": "no-cache",
                            "Expires": "0",
                            "Surrogate-Control": "no-store",
                        },
                    },
                    _e.plugins = [react(), mode === "development" && componentTagger()].filter(Boolean),
                    _e.resolve = {
                        alias: {
                            "@": path.resolve(__dirname, "./src"),
                        },
                    },
                    _e)];
        }
    });
}); });
