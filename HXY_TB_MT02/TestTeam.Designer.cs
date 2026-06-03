using System.Drawing;

namespace Hsg.View
{
    partial class TestTeam
    {
        /// <summary> 
        /// 必需的设计器变量。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清理所有正在使用的资源。
        /// </summary>
        /// <param name="disposing">如果应释放托管资源，为 true；否则为 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 组件设计器生成的代码

        /// <summary> 
        /// 设计器支持所需的方法 - 不要修改
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
            this.m_pal_descript = new System.Windows.Forms.Panel();
            this.m_lb_boardId = new System.Windows.Forms.Label();
            this.buttonA = new System.Windows.Forms.Button();
            this.buttonB = new System.Windows.Forms.Button();
            this.m_txt_test_time = new System.Windows.Forms.Label();
            this.m_txt_description = new System.Windows.Forms.Label();
            this.flowLayoutPanel2 = new System.Windows.Forms.FlowLayoutPanel();
            this.button5 = new System.Windows.Forms.Button();
            this.button6 = new System.Windows.Forms.Button();
            this.button7 = new System.Windows.Forms.Button();
            this.button8 = new System.Windows.Forms.Button();
            this.button13 = new System.Windows.Forms.Button();
            this.button14 = new System.Windows.Forms.Button();
            this.button15 = new System.Windows.Forms.Button();
            this.button16 = new System.Windows.Forms.Button();
            this.button21 = new System.Windows.Forms.Button();
            this.button22 = new System.Windows.Forms.Button();
            this.button23 = new System.Windows.Forms.Button();
            this.button24 = new System.Windows.Forms.Button();
            this.panel1 = new System.Windows.Forms.Panel();
            this.flowLayoutPanel1 = new System.Windows.Forms.FlowLayoutPanel();
            this.button1 = new System.Windows.Forms.Button();
            this.button2 = new System.Windows.Forms.Button();
            this.button3 = new System.Windows.Forms.Button();
            this.button4 = new System.Windows.Forms.Button();
            this.button9 = new System.Windows.Forms.Button();
            this.button10 = new System.Windows.Forms.Button();
            this.button11 = new System.Windows.Forms.Button();
            this.button12 = new System.Windows.Forms.Button();
            this.button17 = new System.Windows.Forms.Button();
            this.button18 = new System.Windows.Forms.Button();
            this.button19 = new System.Windows.Forms.Button();
            this.button20 = new System.Windows.Forms.Button();
            this.panel2 = new System.Windows.Forms.Panel();
            this.m_pal_descript.SuspendLayout();
            this.flowLayoutPanel2.SuspendLayout();
            this.panel1.SuspendLayout();
            this.flowLayoutPanel1.SuspendLayout();
            this.panel2.SuspendLayout();
            this.SuspendLayout();
            // 
            // m_pal_descript
            // 
            this.m_pal_descript.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(30)))), ((int)(((byte)(35)))), ((int)(((byte)(126)))));
            this.m_pal_descript.BackgroundImageLayout = System.Windows.Forms.ImageLayout.Zoom;
            this.m_pal_descript.Controls.Add(this.m_lb_boardId);
            this.m_pal_descript.Controls.Add(this.buttonA);
            this.m_pal_descript.Controls.Add(this.buttonB);
            this.m_pal_descript.Controls.Add(this.m_txt_test_time);
            this.m_pal_descript.Controls.Add(this.m_txt_description);
            this.m_pal_descript.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_pal_descript.Location = new System.Drawing.Point(2, 2);
            this.m_pal_descript.Margin = new System.Windows.Forms.Padding(2);
            this.m_pal_descript.Name = "m_pal_descript";
            this.m_pal_descript.Size = new System.Drawing.Size(86, 68);
            this.m_pal_descript.TabIndex = 13;
            // 
            // m_lb_boardId
            // 
            this.m_lb_boardId.AutoSize = true;
            this.m_lb_boardId.BackColor = System.Drawing.Color.Red;
            this.m_lb_boardId.BorderStyle = System.Windows.Forms.BorderStyle.Fixed3D;
            this.m_lb_boardId.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.m_lb_boardId.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_lb_boardId.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(232)))), ((int)(((byte)(234)))), ((int)(((byte)(246)))));
            this.m_lb_boardId.Location = new System.Drawing.Point(9, 24);
            this.m_lb_boardId.Name = "m_lb_boardId";
            this.m_lb_boardId.Size = new System.Drawing.Size(33, 21);
            this.m_lb_boardId.TabIndex = 0;
            this.m_lb_boardId.Text = "01";
            this.m_lb_boardId.Click += new System.EventHandler(this.OnTeamAlarmClick);
            // 
            // buttonA
            // 
            this.buttonA.BackColor = System.Drawing.Color.LimeGreen;
            this.buttonA.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.buttonA.Font = new System.Drawing.Font("Microsoft Sans Serif", 10.5F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.buttonA.ForeColor = System.Drawing.Color.Black;
            this.buttonA.Location = new System.Drawing.Point(58, 26);
            this.buttonA.Name = "buttonA";
            this.buttonA.Size = new System.Drawing.Size(10, 18);
            this.buttonA.TabIndex = 1;
            this.buttonA.UseVisualStyleBackColor = false;
            this.buttonA.Click += new System.EventHandler(this.On_BoardA_Click);
            // 
            // buttonB
            // 
            this.buttonB.BackColor = System.Drawing.Color.Red;
            this.buttonB.BackgroundImageLayout = System.Windows.Forms.ImageLayout.None;
            this.buttonB.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.buttonB.Font = new System.Drawing.Font("Microsoft Sans Serif", 10.5F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.buttonB.ForeColor = System.Drawing.SystemColors.ActiveCaptionText;
            this.buttonB.Location = new System.Drawing.Point(70, 26);
            this.buttonB.Name = "buttonB";
            this.buttonB.Size = new System.Drawing.Size(10, 18);
            this.buttonB.TabIndex = 1;
            this.buttonB.UseVisualStyleBackColor = false;
            this.buttonB.Click += new System.EventHandler(this.On_BoardB_Click);
            // 
            // m_txt_test_time
            // 
            this.m_txt_test_time.AutoSize = true;
            this.m_txt_test_time.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_test_time.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(232)))), ((int)(((byte)(234)))), ((int)(((byte)(246)))));
            this.m_txt_test_time.Location = new System.Drawing.Point(6, 47);
            this.m_txt_test_time.Name = "m_txt_test_time";
            this.m_txt_test_time.Size = new System.Drawing.Size(74, 21);
            this.m_txt_test_time.TabIndex = 0;
            this.m_txt_test_time.Text = "00:00:00";
            this.m_txt_test_time.UseCompatibleTextRendering = true;
            this.m_txt_test_time.Click += new System.EventHandler(this.OnTimeClick);
            // 
            // m_txt_description
            // 
            this.m_txt_description.AutoSize = true;
            this.m_txt_description.BackColor = System.Drawing.Color.Transparent;
            this.m_txt_description.Font = new System.Drawing.Font("Microsoft Sans Serif", 10.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.m_txt_description.ForeColor = System.Drawing.Color.Lime;
            this.m_txt_description.Location = new System.Drawing.Point(5, 3);
            this.m_txt_description.Name = "m_txt_description";
            this.m_txt_description.Size = new System.Drawing.Size(53, 17);
            this.m_txt_description.TabIndex = 0;
            this.m_txt_description.Text = "不可用";
            this.m_txt_description.Click += new System.EventHandler(this.m_txt_description_Click);
            // 
            // flowLayoutPanel2
            // 
            this.flowLayoutPanel2.BackColor = System.Drawing.SystemColors.Highlight;
            this.flowLayoutPanel2.Controls.Add(this.button5);
            this.flowLayoutPanel2.Controls.Add(this.button6);
            this.flowLayoutPanel2.Controls.Add(this.button7);
            this.flowLayoutPanel2.Controls.Add(this.button8);
            this.flowLayoutPanel2.Controls.Add(this.button13);
            this.flowLayoutPanel2.Controls.Add(this.button14);
            this.flowLayoutPanel2.Controls.Add(this.button15);
            this.flowLayoutPanel2.Controls.Add(this.button16);
            this.flowLayoutPanel2.Controls.Add(this.button21);
            this.flowLayoutPanel2.Controls.Add(this.button22);
            this.flowLayoutPanel2.Controls.Add(this.button23);
            this.flowLayoutPanel2.Controls.Add(this.button24);
            this.flowLayoutPanel2.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.flowLayoutPanel2.Location = new System.Drawing.Point(3, 3);
            this.flowLayoutPanel2.Margin = new System.Windows.Forms.Padding(2);
            this.flowLayoutPanel2.Name = "flowLayoutPanel2";
            this.flowLayoutPanel2.Size = new System.Drawing.Size(131, 62);
            this.flowLayoutPanel2.TabIndex = 12;
            // 
            // button5
            // 
            this.button5.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button5.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button5.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button5.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button5.Location = new System.Drawing.Point(0, 0);
            this.button5.Margin = new System.Windows.Forms.Padding(0);
            this.button5.Name = "button5";
            this.button5.Size = new System.Drawing.Size(32, 20);
            this.button5.TabIndex = 15;
            this.button5.Text = "851";
            this.button5.UseVisualStyleBackColor = false;
            // 
            // button6
            // 
            this.button6.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button6.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button6.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button6.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button6.Location = new System.Drawing.Point(33, 0);
            this.button6.Margin = new System.Windows.Forms.Padding(1, 0, 0, 0);
            this.button6.Name = "button6";
            this.button6.Size = new System.Drawing.Size(32, 20);
            this.button6.TabIndex = 16;
            this.button6.Text = "851";
            this.button6.UseVisualStyleBackColor = false;
            // 
            // button7
            // 
            this.button7.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button7.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button7.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button7.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button7.Location = new System.Drawing.Point(66, 0);
            this.button7.Margin = new System.Windows.Forms.Padding(1, 0, 0, 0);
            this.button7.Name = "button7";
            this.button7.Size = new System.Drawing.Size(32, 20);
            this.button7.TabIndex = 17;
            this.button7.Text = "851";
            this.button7.UseVisualStyleBackColor = false;
            // 
            // button8
            // 
            this.button8.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button8.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button8.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button8.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button8.Location = new System.Drawing.Point(99, 0);
            this.button8.Margin = new System.Windows.Forms.Padding(1, 0, 0, 0);
            this.button8.Name = "button8";
            this.button8.Size = new System.Drawing.Size(32, 20);
            this.button8.TabIndex = 18;
            this.button8.Text = "851";
            this.button8.UseVisualStyleBackColor = false;
            // 
            // button13
            // 
            this.button13.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button13.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button13.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button13.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button13.Location = new System.Drawing.Point(0, 21);
            this.button13.Margin = new System.Windows.Forms.Padding(0, 1, 0, 0);
            this.button13.Name = "button13";
            this.button13.Size = new System.Drawing.Size(32, 20);
            this.button13.TabIndex = 19;
            this.button13.Text = "851";
            this.button13.UseVisualStyleBackColor = false;
            // 
            // button14
            // 
            this.button14.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button14.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button14.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button14.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button14.Location = new System.Drawing.Point(33, 21);
            this.button14.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button14.Name = "button14";
            this.button14.Size = new System.Drawing.Size(32, 20);
            this.button14.TabIndex = 20;
            this.button14.Text = "851";
            this.button14.UseVisualStyleBackColor = false;
            // 
            // button15
            // 
            this.button15.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button15.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button15.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button15.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button15.Location = new System.Drawing.Point(66, 21);
            this.button15.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button15.Name = "button15";
            this.button15.Size = new System.Drawing.Size(32, 20);
            this.button15.TabIndex = 21;
            this.button15.Text = "851";
            this.button15.UseVisualStyleBackColor = false;
            // 
            // button16
            // 
            this.button16.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button16.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button16.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button16.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button16.Location = new System.Drawing.Point(99, 21);
            this.button16.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button16.Name = "button16";
            this.button16.Size = new System.Drawing.Size(32, 20);
            this.button16.TabIndex = 22;
            this.button16.Text = "851";
            this.button16.UseVisualStyleBackColor = false;
            // 
            // button21
            // 
            this.button21.BackColor = System.Drawing.SystemColors.WindowFrame;
            this.button21.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button21.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button21.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button21.Location = new System.Drawing.Point(0, 42);
            this.button21.Margin = new System.Windows.Forms.Padding(0, 1, 0, 0);
            this.button21.Name = "button21";
            this.button21.Size = new System.Drawing.Size(32, 20);
            this.button21.TabIndex = 23;
            this.button21.Text = "851";
            this.button21.UseVisualStyleBackColor = false;
            // 
            // button22
            // 
            this.button22.BackColor = System.Drawing.Color.DimGray;
            this.button22.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button22.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button22.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button22.Location = new System.Drawing.Point(33, 42);
            this.button22.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button22.Name = "button22";
            this.button22.Size = new System.Drawing.Size(32, 20);
            this.button22.TabIndex = 24;
            this.button22.Text = "851";
            this.button22.UseVisualStyleBackColor = false;
            // 
            // button23
            // 
            this.button23.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button23.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button23.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button23.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button23.Location = new System.Drawing.Point(66, 42);
            this.button23.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button23.Name = "button23";
            this.button23.Size = new System.Drawing.Size(32, 20);
            this.button23.TabIndex = 25;
            this.button23.Text = "851";
            this.button23.UseVisualStyleBackColor = false;
            // 
            // button24
            // 
            this.button24.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button24.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button24.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button24.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button24.Location = new System.Drawing.Point(99, 42);
            this.button24.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button24.Name = "button24";
            this.button24.Size = new System.Drawing.Size(32, 20);
            this.button24.TabIndex = 26;
            this.button24.Text = "851";
            this.button24.UseVisualStyleBackColor = false;
            // 
            // panel1
            // 
            this.panel1.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(30)))), ((int)(((byte)(35)))), ((int)(((byte)(126)))));
            this.panel1.Controls.Add(this.flowLayoutPanel1);
            this.panel1.Location = new System.Drawing.Point(88, 2);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(137, 68);
            this.panel1.TabIndex = 14;
            // 
            // flowLayoutPanel1
            // 
            this.flowLayoutPanel1.BackColor = System.Drawing.SystemColors.Highlight;
            this.flowLayoutPanel1.Controls.Add(this.button1);
            this.flowLayoutPanel1.Controls.Add(this.button2);
            this.flowLayoutPanel1.Controls.Add(this.button3);
            this.flowLayoutPanel1.Controls.Add(this.button4);
            this.flowLayoutPanel1.Controls.Add(this.button9);
            this.flowLayoutPanel1.Controls.Add(this.button10);
            this.flowLayoutPanel1.Controls.Add(this.button11);
            this.flowLayoutPanel1.Controls.Add(this.button12);
            this.flowLayoutPanel1.Controls.Add(this.button17);
            this.flowLayoutPanel1.Controls.Add(this.button18);
            this.flowLayoutPanel1.Controls.Add(this.button19);
            this.flowLayoutPanel1.Controls.Add(this.button20);
            this.flowLayoutPanel1.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.flowLayoutPanel1.Location = new System.Drawing.Point(3, 3);
            this.flowLayoutPanel1.Margin = new System.Windows.Forms.Padding(2);
            this.flowLayoutPanel1.Name = "flowLayoutPanel1";
            this.flowLayoutPanel1.Size = new System.Drawing.Size(131, 62);
            this.flowLayoutPanel1.TabIndex = 12;
            // 
            // button1
            // 
            this.button1.BackColor = System.Drawing.Color.Goldenrod;
            this.button1.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button1.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.button1.ForeColor = System.Drawing.Color.White;
            this.button1.Location = new System.Drawing.Point(0, 0);
            this.button1.Margin = new System.Windows.Forms.Padding(0);
            this.button1.Name = "button1";
            this.button1.Size = new System.Drawing.Size(32, 20);
            this.button1.TabIndex = 3;
            this.button1.Text = "851";
            this.button1.UseVisualStyleBackColor = false;

            // 
            // button2
            // 
            this.button2.BackColor = System.Drawing.Color.SlateGray;
            this.button2.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button2.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.button2.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button2.Location = new System.Drawing.Point(33, 0);
            this.button2.Margin = new System.Windows.Forms.Padding(1, 0, 0, 0);
            this.button2.Name = "button2";
            this.button2.Size = new System.Drawing.Size(32, 20);
            this.button2.TabIndex = 4;
            this.button2.Text = "851";
            this.button2.UseVisualStyleBackColor = false;

            // 
            // button3
            // 
            this.button3.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button3.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button3.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.button3.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button3.Location = new System.Drawing.Point(66, 0);
            this.button3.Margin = new System.Windows.Forms.Padding(1, 0, 0, 0);
            this.button3.Name = "button3";
            this.button3.Size = new System.Drawing.Size(32, 20);
            this.button3.TabIndex = 5;
            this.button3.Text = "851";
            this.button3.UseVisualStyleBackColor = false;

            // 
            // button4
            // 
            this.button4.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button4.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button4.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.button4.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button4.Location = new System.Drawing.Point(99, 0);
            this.button4.Margin = new System.Windows.Forms.Padding(1, 0, 0, 0);
            this.button4.Name = "button4";
            this.button4.Size = new System.Drawing.Size(32, 20);
            this.button4.TabIndex = 6;
            this.button4.Text = "851";
            this.button4.UseVisualStyleBackColor = false;

            // 
            // button9
            // 
            this.button9.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button9.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button9.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button9.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button9.Location = new System.Drawing.Point(0, 21);
            this.button9.Margin = new System.Windows.Forms.Padding(0, 1, 0, 0);
            this.button9.Name = "button9";
            this.button9.Size = new System.Drawing.Size(32, 20);
            this.button9.TabIndex = 7;
            this.button9.Text = "851";
            this.button9.UseVisualStyleBackColor = false;

            // 
            // button10
            // 
            this.button10.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button10.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button10.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button10.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button10.Location = new System.Drawing.Point(33, 21);
            this.button10.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button10.Name = "button10";
            this.button10.Size = new System.Drawing.Size(32, 20);
            this.button10.TabIndex = 8;
            this.button10.Text = "851";
            this.button10.UseVisualStyleBackColor = false;

            // 
            // button11
            // 
            this.button11.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button11.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button11.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button11.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button11.Location = new System.Drawing.Point(66, 21);
            this.button11.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button11.Name = "button11";
            this.button11.Size = new System.Drawing.Size(32, 20);
            this.button11.TabIndex = 9;
            this.button11.Text = "851";
            this.button11.UseVisualStyleBackColor = false;

            // 
            // button12
            // 
            this.button12.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button12.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button12.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button12.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button12.Location = new System.Drawing.Point(99, 21);
            this.button12.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button12.Name = "button12";
            this.button12.Size = new System.Drawing.Size(32, 20);
            this.button12.TabIndex = 10;
            this.button12.Text = "851";
            this.button12.UseVisualStyleBackColor = false;

            // 
            // button17
            // 
            this.button17.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button17.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button17.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button17.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button17.Location = new System.Drawing.Point(0, 42);
            this.button17.Margin = new System.Windows.Forms.Padding(0, 1, 0, 0);
            this.button17.Name = "button17";
            this.button17.Size = new System.Drawing.Size(32, 20);
            this.button17.TabIndex = 11;
            this.button17.Text = "851";
            this.button17.UseVisualStyleBackColor = false;
            // 
            // button18
            // 
            this.button18.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button18.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button18.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button18.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button18.Location = new System.Drawing.Point(33, 42);
            this.button18.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button18.Name = "button18";
            this.button18.Size = new System.Drawing.Size(32, 20);
            this.button18.TabIndex = 12;
            this.button18.Text = "851";
            this.button18.UseVisualStyleBackColor = false;
            // 
            // button19
            // 
            this.button19.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button19.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button19.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button19.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button19.Location = new System.Drawing.Point(66, 42);
            this.button19.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button19.Name = "button19";
            this.button19.Size = new System.Drawing.Size(32, 20);
            this.button19.TabIndex = 13;
            this.button19.Text = "851";
            this.button19.UseVisualStyleBackColor = false;
            // 
            // button20
            // 
            this.button20.BackColor = System.Drawing.SystemColors.ControlDarkDark;
            this.button20.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button20.Font = new System.Drawing.Font("Arial", 7.5F, System.Drawing.FontStyle.Bold);
            this.button20.ForeColor = System.Drawing.SystemColors.ControlLightLight;
            this.button20.Location = new System.Drawing.Point(99, 42);
            this.button20.Margin = new System.Windows.Forms.Padding(1, 1, 0, 0);
            this.button20.Name = "button20";
            this.button20.Size = new System.Drawing.Size(32, 20);
            this.button20.TabIndex = 14;
            this.button20.Text = "851";
            this.button20.UseVisualStyleBackColor = false;
            // 
            // panel2
            // 
            this.panel2.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(30)))), ((int)(((byte)(35)))), ((int)(((byte)(126)))));
            this.panel2.Controls.Add(this.flowLayoutPanel2);
            this.panel2.Location = new System.Drawing.Point(221, 2);
            this.panel2.Name = "panel2";
            this.panel2.Size = new System.Drawing.Size(137, 68);
            this.panel2.TabIndex = 14;
            // 
            // TestTeam
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 12F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BackColor = System.Drawing.Color.DarkGray;
            this.Controls.Add(this.panel2);
            this.Controls.Add(this.panel1);
            this.Controls.Add(this.m_pal_descript);
            this.DoubleBuffered = true;
            this.Name = "TestTeam";
            this.Size = new System.Drawing.Size(360, 72);
            this.Load += new System.EventHandler(this.TestTeam_Load);
            this.m_pal_descript.ResumeLayout(false);
            this.m_pal_descript.PerformLayout();
            this.flowLayoutPanel2.ResumeLayout(false);
            this.panel1.ResumeLayout(false);
            this.flowLayoutPanel1.ResumeLayout(false);
            this.panel2.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion
        public System.Windows.Forms.Panel m_pal_descript;
        public System.Windows.Forms.Label m_txt_test_time;
        public System.Windows.Forms.Label m_txt_description;
        public System.Windows.Forms.FlowLayoutPanel flowLayoutPanel2;
        private System.Windows.Forms.Button buttonB;
        private System.Windows.Forms.Button buttonA;
        private System.Windows.Forms.Panel panel1;
        public System.Windows.Forms.FlowLayoutPanel flowLayoutPanel1;
        protected System.Windows.Forms.Button button1;
        private System.Windows.Forms.Panel panel2;
        public System.Windows.Forms.Label m_lb_boardId;
        protected System.Windows.Forms.Button button2;
        protected System.Windows.Forms.Button button3;
        protected System.Windows.Forms.Button button4;
        protected System.Windows.Forms.Button button9;
        protected System.Windows.Forms.Button button10;
        protected System.Windows.Forms.Button button11;
        protected System.Windows.Forms.Button button12;
        protected System.Windows.Forms.Button button17;
        protected System.Windows.Forms.Button button18;
        protected System.Windows.Forms.Button button19;
        protected System.Windows.Forms.Button button20;
        protected System.Windows.Forms.Button button5;
        protected System.Windows.Forms.Button button6;
        protected System.Windows.Forms.Button button7;
        protected System.Windows.Forms.Button button8;
        protected System.Windows.Forms.Button button13;
        protected System.Windows.Forms.Button button14;
        protected System.Windows.Forms.Button button15;
        protected System.Windows.Forms.Button button16;
        protected System.Windows.Forms.Button button21;
        protected System.Windows.Forms.Button button22;
        protected System.Windows.Forms.Button button23;
        protected System.Windows.Forms.Button button24;
    }
}
