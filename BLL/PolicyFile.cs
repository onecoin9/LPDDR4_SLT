using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    public class PolicyParam
    {
        public string Description;
        public string CfgFileName;
        public UInt32 TimeoutMinute;// 
        public UInt32 ExcuteFrequency;// 执行次数
        public UInt32 RepeatMaxFail;// 最大允许失败次数
        public bool RepeatOptimization;// 复测结果优化
        public byte TempFlag;// 温控状态 V1
        public PolicyParam()
        {
            Description = "";
            CfgFileName = "";
            TimeoutMinute = 0;
            ExcuteFrequency = 0;
            RepeatMaxFail = 0;
            RepeatOptimization = false;
        }
        public byte[] Serialize()
        {
            using (MemoryStream ms = new MemoryStream())
            using (BinaryWriter writer = new BinaryWriter(ms))
            {
                WriteString(writer, Description);
                WriteString(writer, CfgFileName);
                writer.Write(TimeoutMinute);
                writer.Write(ExcuteFrequency);
                writer.Write(RepeatMaxFail);
                writer.Write(RepeatOptimization);
                writer.Write(TempFlag);
                return ms.ToArray();
            }
        }
        public static PolicyParam Deserialize(byte[] paramBytes, uint version)
        {
            using (MemoryStream ms = new MemoryStream(paramBytes))
            using (BinaryReader reader = new BinaryReader(ms))
            {
                if (version > 1) // version >1 增加 tempFlag
                {
                    return new PolicyParam
                    {
                        Description = ReadString(reader),
                        CfgFileName = ReadString(reader),
                        TimeoutMinute = reader.ReadUInt32(),
                        ExcuteFrequency = reader.ReadUInt32(),
                        RepeatMaxFail = reader.ReadUInt32(),
                        RepeatOptimization = reader.ReadBoolean(),
                        TempFlag = reader.ReadByte()
                    };
                }
                return new PolicyParam
                {
                    Description = ReadString(reader),
                    CfgFileName = ReadString(reader),
                    TimeoutMinute = reader.ReadUInt32(),
                    ExcuteFrequency = reader.ReadUInt32(),
                    RepeatMaxFail = reader.ReadUInt32(),
                    RepeatOptimization = reader.ReadBoolean()
                };
            }
        }
        public static string ReadString(BinaryReader reader)
        {
            ushort length = reader.ReadUInt16();
            return Encoding.UTF8.GetString(reader.ReadBytes(length));
        }
        private void WriteString(BinaryWriter writer, string s)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(s);
            writer.Write((ushort)bytes.Length);
            writer.Write(bytes);
        }
    }
    public class PolicyMember
    {
        public PolicyParam param;
        public byte[] cfgFileBytes;
        public PolicyMember()
        {
            cfgFileBytes = new byte[0];
            param = new PolicyParam();
        }
        public byte[] SerializeMemberData()
        {
            byte[] paramBytes = param.Serialize();
            byte[] fileData = this.cfgFileBytes;

            using (MemoryStream ms = new MemoryStream())
            using (BinaryWriter writer = new BinaryWriter(ms))
            {
                writer.Write((uint)paramBytes.Length);
                writer.Write(paramBytes);
                writer.Write((uint)fileData.Length);
                writer.Write(fileData);
                return ms.ToArray();
            }
        }

        public static PolicyMember Deserialize(byte[] data, byte tempFlag, uint version)
        {
            using (MemoryStream ms = new MemoryStream(data))
            using (BinaryReader reader = new BinaryReader(ms))
            {
                uint paramLength = reader.ReadUInt32();
                byte[] paramData = reader.ReadBytes((int)paramLength);
                if (paramData == null || paramData.Length != paramLength) // param len error
                {
                    return null;
                }
                PolicyParam param = PolicyParam.Deserialize(paramData, version);
                if (param == null) // decode param erro.
                {
                    return null;
                }
                uint fileDataLength = reader.ReadUInt32();
                byte[] fileData = reader.ReadBytes((int)fileDataLength);
                if (tempFlag != (byte)TempState.TmpMixture)
                {
                    param.TempFlag = tempFlag;
                }
                return new PolicyMember { param = param, cfgFileBytes = fileData };
            }
        }
    }
    /*
     version 01 first version
     version 02 PolicyParam add  TempFlag
    */
    public class PolicyFile
    {
        private const UInt32 MAGIC_ID = 0x46544d46;
        private List<PolicyMember> _memberList = new List<PolicyMember>();
        public List<PolicyMember> MemberList { get { return _memberList; } }
        public UInt32 Timestamp { get; private set; }
        public UInt32 TempFlag;// 温控状态
        private const uint Version = 0x0002;
        public void SaveToFile(string path)
        {
            Timestamp = Tools.GetTimestampToSecond();
            using (FileStream fs = new FileStream(path, FileMode.Create))
            using (BinaryWriter writer = new BinaryWriter(fs))
            {
                writer.Write((UInt32)MAGIC_ID); // Magic
                writer.Write((uint)Version); // Version
                writer.Write((uint)Timestamp); // file Timestamp
                writer.Write(TempFlag);
                writer.Write((uint)_memberList.Count); // Member count

                foreach (var member in _memberList)
                {
                    byte[] data = member.SerializeMemberData();
                    uint length = (uint)data.Length;
                    byte[] lengthBytes = BitConverter.GetBytes(length);
                    writer.Write(length);
                    writer.Write(data);
                }

                // Compute total SHA256 hash
                fs.Position = 0;
                byte[] fileData = new byte[fs.Length];
                fs.Read(fileData, 0, (int)fs.Length);
                byte[] hash = SHA256.Create().ComputeHash(fileData, 0, (int)fs.Length);
                writer.Write(hash);
            }
        }
        public void AddMember(PolicyMember member)
        {
            _memberList.Add(member);
        }

        public static PolicyFile Deserialize(string path, ref string errorMsg)
        {
            try
            {
                using (FileStream fs = new FileStream(path, FileMode.Open))
                {
                    byte[] fileData = new byte[fs.Length];
                    fs.Read(fileData, 0, (int)fs.Length);
                    byte[] targetHash = SHA256.Create().ComputeHash(fileData, 0, (int)fs.Length - 32);
                    byte[] checkSha256 = new byte[32];
                    //fs.Read(checkSha256, (int)fs.Length - 32, 32);
                    Array.Copy(fileData, (int)fs.Length - 32, checkSha256, 0, 32);
                    if (!checkSha256.SequenceEqual(targetHash))
                    {
                        errorMsg = "sha256 error";
                        return null;
                    }
                    fs.Seek(0, SeekOrigin.Begin);
                    using (BinaryReader reader = new BinaryReader(fs))
                    {
                        UInt32 magicId = reader.ReadUInt32();
                        UInt32 version = reader.ReadUInt32();
                        UInt32 timestamp = reader.ReadUInt32();
                        UInt32 tempFlag = reader.ReadUInt32();
                        UInt32 memberCount = reader.ReadUInt32();
                        if (tempFlag != (UInt32)TempState.TmpHight &&
                            tempFlag != (UInt32)TempState.TmpMixture &&
                            tempFlag != (UInt32)TempState.TmpNormal)
                        {
                            errorMsg = "not support enviroment";
                            return null;
                        }
                        if (magicId != MAGIC_ID) //  magic error
                        {
                            errorMsg = "magic error";
                            return null;
                        }
                        if (memberCount == 0)
                        {
                            errorMsg = "memberCount error";
                            return null;
                        }


                        PolicyFile obj = new PolicyFile();
                        obj.Timestamp = timestamp;
                        obj.TempFlag = tempFlag;
                        for (UInt32 i = 0; i < memberCount; i++)
                        {
                            uint memberLen = reader.ReadUInt32();
                            byte[] memberData = reader.ReadBytes((int)memberLen);
                            PolicyMember member = PolicyMember.Deserialize(memberData, (byte)tempFlag, version);
                            if (member == null)// parse member failed.
                            {
                                errorMsg = "parse mem error";
                                return null;
                            }
                            obj.AddMember(member);
                        }
                        return obj;
                    }
                }

            }
            catch (Exception ex)
            {
                // Console.WriteLine(ex.Message);
                errorMsg = ex.Message;
            }
            return null;

        }
    }
}
