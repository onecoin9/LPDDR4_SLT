using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    /// <summary>
    /// Handler 通讯协议（JSON 编解码见 HCProtocol.Json.cs）
    /// </summary>
    public partial class HCProtocol
    {
        public const byte ERROR_NONE = 0x00;
        public const byte ERROR_MODE = 0x01;
        public const byte ERROR_PARAM = 0x02;
        public const byte ERROR_OTHER = 0x03;
        public const byte ERROR_WAIT = 0x04;
    }
}
