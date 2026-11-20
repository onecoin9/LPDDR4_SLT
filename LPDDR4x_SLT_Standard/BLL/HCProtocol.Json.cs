using System;
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json;

namespace Hsg.BLL
{
    /// <summary>
    /// Handler JSON 通信协议（与 SDK_TB_MT02 BLL\Model 侧用法一致）
    /// </summary>
    public partial class HCProtocol
    {
        public const string M_GET_VERSION = "getversion";
        public const string M_LOT_START = "lotstart";
        public const string M_LOT_END = "lotend";
        public const string M_TEST_START = "teststart";
        public const string M_TEST_END = "testend";
        public const string M_ALARM = "alarm";
        public const string M_SWITCH = "switch";
        public const string M_SET_MACHINE_ACTION = "setmachineaction";
        public const string M_GET_MACHINE_ACTION = "getmachineaction";

        public class JsonRequest
        {
            [JsonProperty("method")]
            public string Method { get; set; }
            [JsonProperty("data")]
            public object Data { get; set; }
        }

        public class JsonResponse
        {
            [JsonProperty("method")]
            public string Method { get; set; }
            [JsonProperty("status")]
            public string Status { get; set; }
            [JsonProperty("data")]
            public object Data { get; set; }
        }

        public class TestEndData
        {
            [JsonProperty("bibid")]
            public int BibId { get; set; }
            [JsonProperty("sites")]
            public List<TestEndSite> Sites { get; set; } = new List<TestEndSite>();
        }

        public class TestEndSite
        {
            [JsonProperty("siteid")]
            public int SiteId { get; set; }
            [JsonProperty("result")]
            public int Result { get; set; }
        }

        public class AlarmData
        {
            [JsonProperty("message")]
            public string Message { get; set; }
        }

        /// <summary>
        /// lotstart 请求数据（Handler → Tester，文档 Section 四.1.2）
        /// </summary>
        public class LotStartData
        {
            [JsonProperty("lotid")]
            public string LotId { get; set; }
            [JsonProperty("productid")]
            public string ProductId { get; set; }
            [JsonProperty("recipe")]
            public string Recipe { get; set; }
            [JsonProperty("hardware")]
            public string Hardware { get; set; }
            [JsonProperty("operator")]
            public string Operator { get; set; }
            [JsonProperty("selfcheck")]
            public bool SelfCheck { get; set; }
        }

        /// <summary>
        /// setenable 数组元素
        /// </summary>
        public class SetEnableItem
        {
            [JsonProperty("bibid")]
            public int BibId { get; set; }
            [JsonProperty("enable")]
            public string Enable { get; set; }
        }

        /// <summary>
        /// teststart 请求数据（Handler → Tester，文档 Section 四.1.5）
        /// </summary>
        public class TestStartData
        {
            [JsonProperty("bibid")]
            public int BibId { get; set; }
            [JsonProperty("sites")]
            public List<TestStartSite> Sites { get; set; } = new List<TestStartSite>();
        }

        public class TestStartSite
        {
            [JsonProperty("siteid")]
            public int SiteId { get; set; }
            [JsonProperty("IsEnable")]
            public bool IsEnable { get; set; }
            [JsonProperty("sitesn")]
            public string SiteSn { get; set; }
            [JsonProperty("SocketSN")]
            public string SocketSn { get; set; }
        }

        private static readonly JsonSerializerSettings JsonSettings = new JsonSerializerSettings
        {
            NullValueHandling = NullValueHandling.Ignore
        };

        public static byte[] EncodeJsonRequestBytes(string method, object data)
        {
            var req = new JsonRequest
            {
                Method = method,
                Data = data ?? new { }
            };
            string json = JsonConvert.SerializeObject(req, Formatting.None, JsonSettings);
            return Encoding.UTF8.GetBytes(json);
        }

        public static byte[] EncodeJsonResponseBytes(string method, string status, object data)
        {
            var resp = new JsonResponse
            {
                Method = method,
                Status = status,
                Data = data ?? new { }
            };
            string json = JsonConvert.SerializeObject(resp, Formatting.None, JsonSettings);
            return Encoding.UTF8.GetBytes(json);
        }

        public static bool TryDecodeJsonRequest(byte[] raw, out JsonRequest req, out string err)
        {
            req = null;
            err = "";
            try
            {
                var json = Encoding.UTF8.GetString(raw).Trim('\0', '\r', '\n', ' ');
                req = JsonConvert.DeserializeObject<JsonRequest>(json);
                if (req == null || string.IsNullOrWhiteSpace(req.Method))
                {
                    err = "invalid request: method empty";
                    return false;
                }
                return true;
            }
            catch (Exception ex)
            {
                err = ex.Message;
                return false;
            }
        }

        public static bool TryDecodeJsonResponse(byte[] raw, out JsonResponse resp, out string err)
        {
            resp = null;
            err = "";
            try
            {
                var json = Encoding.UTF8.GetString(raw).Trim('\0', '\r', '\n', ' ');
                resp = JsonConvert.DeserializeObject<JsonResponse>(json);
                if (resp == null
                    || string.IsNullOrWhiteSpace(resp.Method)
                    || string.IsNullOrWhiteSpace(resp.Status))
                {
                    err = "invalid response: method/status empty";
                    return false;
                }
                return true;
            }
            catch (Exception ex)
            {
                err = ex.Message;
                return false;
            }
        }

        public static byte[] EncodeTestEndJson(int bibId, IList<int> siteResults)
        {
            var data = new TestEndData { BibId = bibId };
            for (int i = 0; i < siteResults.Count; i++)
            {
                data.Sites.Add(new TestEndSite
                {
                    SiteId = i + 1,
                    Result = siteResults[i]
                });
            }
            return EncodeJsonRequestBytes(M_TEST_END, data);
        }

        public static byte[] EncodeAlarmJson(string message)
        {
            var data = new AlarmData { Message = message ?? "" };
            return EncodeJsonRequestBytes(M_ALARM, data);
        }

        /// <summary>
        /// 编码 lotstart 成功响应（含 setenable）
        /// </summary>
        public static byte[] EncodeLotStartResponse(bool success, List<SetEnableItem> setEnable = null)
        {
            object data;
            if (setEnable != null && setEnable.Count > 0)
            {
                data = new { setenable = setEnable };
            }
            else
            {
                data = new { };
            }
            return EncodeJsonResponseBytes(M_LOT_START, success ? "success" : "fail", data);
        }

        /// <summary>
        /// 编码 teststart 响应
        /// </summary>
        public static byte[] EncodeTestStartResponse(bool success, string reason = null)
        {
            object data;
            if (!string.IsNullOrWhiteSpace(reason))
            {
                data = new { reason };
            }
            else
            {
                data = new { };
            }
            return EncodeJsonResponseBytes(M_TEST_START, success ? "success" : "fail", data);
        }
    }
}
