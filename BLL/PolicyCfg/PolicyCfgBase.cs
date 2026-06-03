using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Policy
{
    //策略的配置文件
    public abstract class PolicyCfgBase
    {
        //  protected string _filePath;
        protected string _fileName;
        public abstract bool IsEncrypt();
        public virtual string GetFileName()
        {
            return _fileName;
        }
      
        public virtual UInt32 GetTimeout()
        {
            return 0;
        }

        public virtual UInt32 GetExecuteFrequency()
        {
            return 0;
        }

        public virtual string GetExtraDetail()
        {
            return "";
        }
        //public abstract bool CheckFileIsValid(string filePath);
        public abstract bool ReadEmiContent(ref byte[] outData);
        
    }
}
