using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net.NetworkInformation;
using System.Net;

namespace TBM01.TOOL
{
    public class TOOL
    {
        static bool PingIp(string ip, int mseconde)
        {
            Ping p = new Ping();
            byte[] sendData = new byte[2] { 0x88, 0x88 };
            PingOptions opts = new PingOptions();
            opts.DontFragment = true;
            PingReply reply = p.Send(IPAddress.Parse(ip), mseconde, sendData);
            if (reply.Status == IPStatus.Success)
            {
                return true;
            }
            return false;
        }

        static string HexToString(byte[] data)
        {
            var hexBuilder = new StringBuilder(data.Length * 2);
            foreach(var v in data)
            {
                hexBuilder.AppendFormat("0:x2", v);
            }
            string hexStr = String.Format(@"{0}", hexBuilder);
            return hexStr;
        }
    }
}
