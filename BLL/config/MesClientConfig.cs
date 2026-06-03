using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{
    class MesClientConfig
    {
        public string IPAddr = "127.0.0.1";
        public ushort Port = 9900;
        public MesClientConfig()
        {
            SysConfig sysconfig = SysConfig.GetInstance();
            IPAddr = sysconfig.MesServiceAddr.Value;
            ushort.TryParse(sysconfig.MesServicePort.Value, out Port);
        }
    }
}
