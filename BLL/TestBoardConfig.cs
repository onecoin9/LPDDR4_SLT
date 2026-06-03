using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.IO;
using System.Text.RegularExpressions;

namespace Hsg.BLL
{
    public class TestBoardConfig
    {
        public byte[] ConfigBytes { get; }
        public ushort AginTime { get; }
        public TestBoardConfig(byte [] configBytes)
        {
            ConfigBytes = configBytes;
            string content = ASCIIEncoding.Default.GetString(configBytes);
            using (StringReader reader = new StringReader(content))
            {
                string line = reader.ReadLine();

                while (line != null && line.Length > 0)
                {
                    Match ma = Regex.Match(line, @"AgingTime=\d+");
                    if (ma != null && ma.Value.Length > 0)
                    {
                        AginTime = ushort.Parse(ma.Value.Substring(10));
                        break;
                    }
                    line = reader.ReadLine();
                }
            }
        }
    }
}
