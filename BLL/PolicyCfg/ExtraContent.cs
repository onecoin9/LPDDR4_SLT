using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Policy
{
    public class ExtraContent
    {
        private string _name;
        public String Name
        {
            get { return _name; }
            set
            {
                _name = value;
            }
        }

        private UInt32 _volume;
        public UInt32 Volume
        {
            get { return _volume; }
            set { _volume = value; }
        }
        public const string Copyright = "www.hosinglobal.com";

        private string _description;
        public string Description
        {
            get { return _description; }
            set { _description = value; }
        }
        private UInt32 _timeout;
        public UInt32 Timeout
        {
            get { return _timeout; }
            set { _timeout = value; }
        }
        private UInt32 _executeFrequency = 0;
        public UInt32 ExecuteFrequency
        {
            get { return _executeFrequency; }
            set { _executeFrequency = value; }
        }
        public static ExtraContent LoadContent(string jsonContent)
        {
            ExtraContent parsedObject = null;
            try
            {
                parsedObject = (ExtraContent)JsonConvert.DeserializeObject<ExtraContent>(jsonContent);
            }
            catch

            {
                return null;
            }
            return parsedObject;
        }
        public string ToJsonString()
        {
            string json = JsonConvert.SerializeObject(this);
            return json;
        }

        public string ToFormatString()
        {
            string format = "Name:" + Name + "\r\n";
            format += "Volume:" + Volume + "\r\n";
            format += "Timeout:" + Timeout + "\r\n";
            format += "Detail:" + "\r\n" + Description;
            return format;
        }
    }
}


