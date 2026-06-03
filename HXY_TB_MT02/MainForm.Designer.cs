using System.Drawing;

namespace Hsg.View
{
    partial class MainForm
    {
        private static Color BG_COLOR = Color.FromArgb(73, 106, 160);//(41, 66, 107);
        public const int BG_R = 26;
        public const int BG_G = 35;
        public const int BG_B = 126;
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.components = new System.ComponentModel.Container();
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(MainForm));
            this.panel1 = new System.Windows.Forms.Panel();
            this.m_txt_work_time = new System.Windows.Forms.Label();
            this.m_txt_work_mode = new System.Windows.Forms.Label();
            this.m_btn_pause = new System.Windows.Forms.Button();
            this.m_btn_start = new System.Windows.Forms.Button();
            this.m_btn_setting = new System.Windows.Forms.Button();
            this.m_btn_exit = new System.Windows.Forms.Button();
            this.m_bnt_title = new System.Windows.Forms.Button();
            this.pictureBox1 = new System.Windows.Forms.PictureBox();
            this.panel2 = new System.Windows.Forms.Panel();
            this.m_pal_bottom_tab = new System.Windows.Forms.Panel();
            this.panel6 = new System.Windows.Forms.Panel();
            this.m_txt_emi_path = new System.Windows.Forms.Label();
            this.label5 = new System.Windows.Forms.Label();
            this.splitter6 = new System.Windows.Forms.Splitter();
            this.panel5 = new System.Windows.Forms.Panel();
            this.m_txt_test_tatistics = new System.Windows.Forms.Label();
            this.label4 = new System.Windows.Forms.Label();
            this.splitter5 = new System.Windows.Forms.Splitter();
            this.panel4 = new System.Windows.Forms.Panel();
            this.m_txt_workStage = new System.Windows.Forms.Label();
            this.label11 = new System.Windows.Forms.Label();
            this.splitter4 = new System.Windows.Forms.Splitter();
            this.panel3 = new System.Windows.Forms.Panel();
            this.m_txt_online_team = new System.Windows.Forms.Label();
            this.label9 = new System.Windows.Forms.Label();
            this.splitter3 = new System.Windows.Forms.Splitter();
            this.m_pal_bottom_sub2 = new System.Windows.Forms.Panel();
            this.m_txt_service_state = new System.Windows.Forms.Label();
            this.label8 = new System.Windows.Forms.Label();
            this.splitter2 = new System.Windows.Forms.Splitter();
            this.m_pal_bottom_sub1 = new System.Windows.Forms.Panel();
            this.m_txt_conn_state = new System.Windows.Forms.Label();
            this.label7 = new System.Windows.Forms.Label();
            this.m_pal_order_log = new System.Windows.Forms.Panel();
            this.m_rtb_log = new System.Windows.Forms.RichTextBox();
            this.label3 = new System.Windows.Forms.Label();
            this.label2 = new System.Windows.Forms.Label();
            this.m_txt_test_workOrder = new System.Windows.Forms.Label();
            this.m_txt_material_no = new System.Windows.Forms.Label();
            this.m_txt_order_no = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.splitter1 = new System.Windows.Forms.Splitter();
            this.m_pal_center = new System.Windows.Forms.Panel();
            this.m_pnl_statusList = new System.Windows.Forms.Panel();
            this.m_pal_status_pal_bar = new System.Windows.Forms.Panel();
            this.m_bgw_ui_update = new System.ComponentModel.BackgroundWorker();
            this.m_richbox_update_timer = new System.Windows.Forms.Timer(this.components);
            this.panel1.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.pictureBox1)).BeginInit();
            this.panel2.SuspendLayout();
            this.m_pal_bottom_tab.SuspendLayout();
            this.panel6.SuspendLayout();
            this.panel5.SuspendLayout();
            this.panel4.SuspendLayout();
            this.panel3.SuspendLayout();
            this.m_pal_bottom_sub2.SuspendLayout();
            this.m_pal_bottom_sub1.SuspendLayout();
            this.m_pal_order_log.SuspendLayout();
            this.m_pal_center.SuspendLayout();
            this.SuspendLayout();
            // 
            // panel1
            // 
            this.panel1.BackColor = System.Drawing.SystemColors.Control;
            this.panel1.Controls.Add(this.m_txt_work_time);
            this.panel1.Controls.Add(this.m_txt_work_mode);
            this.panel1.Controls.Add(this.m_btn_pause);
            this.panel1.Controls.Add(this.m_btn_start);
            this.panel1.Controls.Add(this.m_btn_setting);
            this.panel1.Controls.Add(this.m_btn_exit);
            this.panel1.Controls.Add(this.m_bnt_title);
            this.panel1.Controls.Add(this.pictureBox1);
            this.panel1.Dock = System.Windows.Forms.DockStyle.Top;
            this.panel1.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.panel1.Location = new System.Drawing.Point(4, 4);
            this.panel1.Margin = new System.Windows.Forms.Padding(2, 0, 2, 2);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(1274, 102);
            this.panel1.TabIndex = 2;
            // 
            // m_txt_work_time
            // 
            this.m_txt_work_time.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Right)));
            this.m_txt_work_time.AutoSize = true;
            this.m_txt_work_time.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(26)))), ((int)(((byte)(35)))), ((int)(((byte)(126)))));
            this.m_txt_work_time.Font = new System.Drawing.Font("微软雅黑", 15.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_work_time.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(232)))), ((int)(((byte)(234)))), ((int)(((byte)(246)))));
            this.m_txt_work_time.Location = new System.Drawing.Point(840, 70);
            this.m_txt_work_time.Margin = new System.Windows.Forms.Padding(3, 0, 10, 0);
            this.m_txt_work_time.Name = "m_txt_work_time";
            this.m_txt_work_time.Size = new System.Drawing.Size(106, 28);
            this.m_txt_work_time.TabIndex = 19;
            this.m_txt_work_time.Text = "000:00:00";
            // 
            // m_txt_work_mode
            // 
            this.m_txt_work_mode.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.m_txt_work_mode.AutoSize = true;
            this.m_txt_work_mode.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(26)))), ((int)(((byte)(35)))), ((int)(((byte)(126)))));
            this.m_txt_work_mode.Font = new System.Drawing.Font("楷体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_work_mode.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(232)))), ((int)(((byte)(234)))), ((int)(((byte)(246)))));
            this.m_txt_work_mode.Location = new System.Drawing.Point(840, 11);
            this.m_txt_work_mode.Margin = new System.Windows.Forms.Padding(3, 0, 10, 0);
            this.m_txt_work_mode.Name = "m_txt_work_mode";
            this.m_txt_work_mode.Size = new System.Drawing.Size(93, 19);
            this.m_txt_work_mode.TabIndex = 20;
            this.m_txt_work_mode.Text = "调试模式";
            // 
            // m_btn_pause
            // 
            this.m_btn_pause.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.m_btn_pause.BackColor = System.Drawing.Color.White;
            this.m_btn_pause.Enabled = false;
            this.m_btn_pause.Image = ((System.Drawing.Image)(resources.GetObject("m_btn_pause.Image")));
            this.m_btn_pause.Location = new System.Drawing.Point(1032, 0);
            this.m_btn_pause.Name = "m_btn_pause";
            this.m_btn_pause.Size = new System.Drawing.Size(80, 68);
            this.m_btn_pause.TabIndex = 15;
            this.m_btn_pause.UseVisualStyleBackColor = false;
            this.m_btn_pause.Click += new System.EventHandler(this.m_btn_pause_Click);
            // 
            // m_btn_start
            // 
            this.m_btn_start.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.m_btn_start.BackColor = System.Drawing.Color.White;
            this.m_btn_start.Image = ((System.Drawing.Image)(resources.GetObject("m_btn_start.Image")));
            this.m_btn_start.Location = new System.Drawing.Point(952, 0);
            this.m_btn_start.Name = "m_btn_start";
            this.m_btn_start.Size = new System.Drawing.Size(80, 68);
            this.m_btn_start.TabIndex = 16;
            this.m_btn_start.UseVisualStyleBackColor = false;
            this.m_btn_start.Click += new System.EventHandler(this.m_btn_start_Click);
            // 
            // m_btn_setting
            // 
            this.m_btn_setting.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.m_btn_setting.Image = ((System.Drawing.Image)(resources.GetObject("m_btn_setting.Image")));
            this.m_btn_setting.Location = new System.Drawing.Point(1112, 0);
            this.m_btn_setting.Name = "m_btn_setting";
            this.m_btn_setting.Size = new System.Drawing.Size(80, 68);
            this.m_btn_setting.TabIndex = 18;
            this.m_btn_setting.UseVisualStyleBackColor = true;
            this.m_btn_setting.Click += new System.EventHandler(this.m_btn_setting_Click);
            // 
            // m_btn_exit
            // 
            this.m_btn_exit.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.m_btn_exit.Cursor = System.Windows.Forms.Cursors.Default;
            this.m_btn_exit.DialogResult = System.Windows.Forms.DialogResult.Cancel;
            this.m_btn_exit.Image = ((System.Drawing.Image)(resources.GetObject("m_btn_exit.Image")));
            this.m_btn_exit.Location = new System.Drawing.Point(1192, 0);
            this.m_btn_exit.Name = "m_btn_exit";
            this.m_btn_exit.Size = new System.Drawing.Size(80, 68);
            this.m_btn_exit.TabIndex = 17;
            this.m_btn_exit.UseVisualStyleBackColor = true;
            this.m_btn_exit.Click += new System.EventHandler(this.m_btn_exit_Click);
            // 
            // m_bnt_title
            // 
            this.m_bnt_title.Anchor = ((System.Windows.Forms.AnchorStyles)(((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.m_bnt_title.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(26)))), ((int)(((byte)(35)))), ((int)(((byte)(126)))));
            this.m_bnt_title.CausesValidation = false;
            this.m_bnt_title.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.m_bnt_title.Font = new System.Drawing.Font("新宋体", 26.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_bnt_title.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(232)))), ((int)(((byte)(234)))), ((int)(((byte)(246)))));
            this.m_bnt_title.Location = new System.Drawing.Point(309, 0);
            this.m_bnt_title.Margin = new System.Windows.Forms.Padding(0, 1, 0, 1);
            this.m_bnt_title.Name = "m_bnt_title";
            this.m_bnt_title.Size = new System.Drawing.Size(640, 67);
            this.m_bnt_title.TabIndex = 14;
            this.m_bnt_title.Text = "测试控制系统";
            this.m_bnt_title.UseVisualStyleBackColor = false;
            this.m_bnt_title.Click += new System.EventHandler(this.OnMainFormClick);
            // 
            // pictureBox1
            // 
            this.pictureBox1.BackColor = System.Drawing.SystemColors.ButtonHighlight;
            this.pictureBox1.Image = ((System.Drawing.Image)(resources.GetObject("pictureBox1.Image")));
            this.pictureBox1.Location = new System.Drawing.Point(0, 0);
            this.pictureBox1.Margin = new System.Windows.Forms.Padding(2, 2, 0, 2);
            this.pictureBox1.Name = "pictureBox1";
            this.pictureBox1.Size = new System.Drawing.Size(307, 68);
            this.pictureBox1.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom;
            this.pictureBox1.TabIndex = 13;
            this.pictureBox1.TabStop = false;
            this.pictureBox1.Click += new System.EventHandler(this.pictureBox1_Click);
            // 
            // panel2
            // 
            this.panel2.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.panel2.Controls.Add(this.m_pal_bottom_tab);
            this.panel2.Controls.Add(this.m_pal_order_log);
            this.panel2.Dock = System.Windows.Forms.DockStyle.Bottom;
            this.panel2.Location = new System.Drawing.Point(4, 562);
            this.panel2.Margin = new System.Windows.Forms.Padding(2, 2, 2, 2);
            this.panel2.Name = "panel2";
            this.panel2.Size = new System.Drawing.Size(1274, 156);
            this.panel2.TabIndex = 3;
            // 
            // m_pal_bottom_tab
            // 
            this.m_pal_bottom_tab.BackColor = System.Drawing.SystemColors.ButtonHighlight;
            this.m_pal_bottom_tab.Controls.Add(this.panel6);
            this.m_pal_bottom_tab.Controls.Add(this.splitter6);
            this.m_pal_bottom_tab.Controls.Add(this.panel5);
            this.m_pal_bottom_tab.Controls.Add(this.splitter5);
            this.m_pal_bottom_tab.Controls.Add(this.panel4);
            this.m_pal_bottom_tab.Controls.Add(this.splitter4);
            this.m_pal_bottom_tab.Controls.Add(this.panel3);
            this.m_pal_bottom_tab.Controls.Add(this.splitter3);
            this.m_pal_bottom_tab.Controls.Add(this.m_pal_bottom_sub2);
            this.m_pal_bottom_tab.Controls.Add(this.splitter2);
            this.m_pal_bottom_tab.Controls.Add(this.m_pal_bottom_sub1);
            this.m_pal_bottom_tab.Dock = System.Windows.Forms.DockStyle.Bottom;
            this.m_pal_bottom_tab.Location = new System.Drawing.Point(0, 121);
            this.m_pal_bottom_tab.Name = "m_pal_bottom_tab";
            this.m_pal_bottom_tab.Size = new System.Drawing.Size(1274, 35);
            this.m_pal_bottom_tab.TabIndex = 1;
            // 
            // panel6
            // 
            this.panel6.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.panel6.Controls.Add(this.m_txt_emi_path);
            this.panel6.Controls.Add(this.label5);
            this.panel6.Dock = System.Windows.Forms.DockStyle.Fill;
            this.panel6.Location = new System.Drawing.Point(985, 0);
            this.panel6.Name = "panel6";
            this.panel6.Size = new System.Drawing.Size(289, 35);
            this.panel6.TabIndex = 10;
            // 
            // m_txt_emi_path
            // 
            this.m_txt_emi_path.AutoSize = true;
            this.m_txt_emi_path.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_emi_path.Location = new System.Drawing.Point(117, 9);
            this.m_txt_emi_path.Name = "m_txt_emi_path";
            this.m_txt_emi_path.Size = new System.Drawing.Size(53, 19);
            this.m_txt_emi_path.TabIndex = 26;
            this.m_txt_emi_path.Text = "path";
            // 
            // label5
            // 
            this.label5.AutoSize = true;
            this.label5.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label5.Location = new System.Drawing.Point(10, 9);
            this.label5.Name = "label5";
            this.label5.Size = new System.Drawing.Size(104, 19);
            this.label5.TabIndex = 25;
            this.label5.Text = "配置文件:";
            // 
            // splitter6
            // 
            this.splitter6.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.splitter6.Location = new System.Drawing.Point(982, 0);
            this.splitter6.Name = "splitter6";
            this.splitter6.Size = new System.Drawing.Size(3, 35);
            this.splitter6.TabIndex = 9;
            this.splitter6.TabStop = false;
            // 
            // panel5
            // 
            this.panel5.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.panel5.Controls.Add(this.m_txt_test_tatistics);
            this.panel5.Controls.Add(this.label4);
            this.panel5.Dock = System.Windows.Forms.DockStyle.Left;
            this.panel5.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.panel5.Location = new System.Drawing.Point(701, 0);
            this.panel5.Name = "panel5";
            this.panel5.Size = new System.Drawing.Size(281, 35);
            this.panel5.TabIndex = 8;
            // 
            // m_txt_test_tatistics
            // 
            this.m_txt_test_tatistics.AutoSize = true;
            this.m_txt_test_tatistics.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_test_tatistics.Location = new System.Drawing.Point(73, 9);
            this.m_txt_test_tatistics.Name = "m_txt_test_tatistics";
            this.m_txt_test_tatistics.Size = new System.Drawing.Size(196, 19);
            this.m_txt_test_tatistics.TabIndex = 24;
            this.m_txt_test_tatistics.Text = "111/10000(99.91%)";
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label4.Location = new System.Drawing.Point(7, 9);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(64, 19);
            this.label4.TabIndex = 23;
            this.label4.Text = "Pass:";
            // 
            // splitter5
            // 
            this.splitter5.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.splitter5.Location = new System.Drawing.Point(698, 0);
            this.splitter5.Name = "splitter5";
            this.splitter5.Size = new System.Drawing.Size(3, 35);
            this.splitter5.TabIndex = 7;
            this.splitter5.TabStop = false;
            // 
            // panel4
            // 
            this.panel4.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.panel4.Controls.Add(this.m_txt_workStage);
            this.panel4.Controls.Add(this.label11);
            this.panel4.Dock = System.Windows.Forms.DockStyle.Left;
            this.panel4.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.panel4.Location = new System.Drawing.Point(504, 0);
            this.panel4.Name = "panel4";
            this.panel4.Size = new System.Drawing.Size(194, 35);
            this.panel4.TabIndex = 6;
            // 
            // m_txt_workStage
            // 
            this.m_txt_workStage.AutoSize = true;
            this.m_txt_workStage.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_workStage.Location = new System.Drawing.Point(73, 9);
            this.m_txt_workStage.Name = "m_txt_workStage";
            this.m_txt_workStage.Size = new System.Drawing.Size(93, 19);
            this.m_txt_workStage.TabIndex = 20;
            this.m_txt_workStage.Text = "首次测试";
            // 
            // label11
            // 
            this.label11.AutoSize = true;
            this.label11.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label11.Location = new System.Drawing.Point(9, 9);
            this.label11.Name = "label11";
            this.label11.Size = new System.Drawing.Size(62, 19);
            this.label11.TabIndex = 19;
            this.label11.Text = "工序:";
            // 
            // splitter4
            // 
            this.splitter4.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.splitter4.Location = new System.Drawing.Point(501, 0);
            this.splitter4.Name = "splitter4";
            this.splitter4.Size = new System.Drawing.Size(3, 35);
            this.splitter4.TabIndex = 5;
            this.splitter4.TabStop = false;
            // 
            // panel3
            // 
            this.panel3.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.panel3.Controls.Add(this.m_txt_online_team);
            this.panel3.Controls.Add(this.label9);
            this.panel3.Dock = System.Windows.Forms.DockStyle.Left;
            this.panel3.Location = new System.Drawing.Point(346, 0);
            this.panel3.Name = "panel3";
            this.panel3.Size = new System.Drawing.Size(155, 35);
            this.panel3.TabIndex = 4;
            // 
            // m_txt_online_team
            // 
            this.m_txt_online_team.AutoSize = true;
            this.m_txt_online_team.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_online_team.Location = new System.Drawing.Point(79, 9);
            this.m_txt_online_team.Name = "m_txt_online_team";
            this.m_txt_online_team.Size = new System.Drawing.Size(64, 19);
            this.m_txt_online_team.TabIndex = 10;
            this.m_txt_online_team.Text = "32/32";
            // 
            // label9
            // 
            this.label9.AutoSize = true;
            this.label9.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label9.Location = new System.Drawing.Point(12, 9);
            this.label9.Name = "label9";
            this.label9.Size = new System.Drawing.Size(62, 19);
            this.label9.TabIndex = 11;
            this.label9.Text = "在线:";
            // 
            // splitter3
            // 
            this.splitter3.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.splitter3.Location = new System.Drawing.Point(343, 0);
            this.splitter3.Name = "splitter3";
            this.splitter3.Size = new System.Drawing.Size(3, 35);
            this.splitter3.TabIndex = 3;
            this.splitter3.TabStop = false;
            // 
            // m_pal_bottom_sub2
            // 
            this.m_pal_bottom_sub2.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.m_pal_bottom_sub2.Controls.Add(this.m_txt_service_state);
            this.m_pal_bottom_sub2.Controls.Add(this.label8);
            this.m_pal_bottom_sub2.Dock = System.Windows.Forms.DockStyle.Left;
            this.m_pal_bottom_sub2.Location = new System.Drawing.Point(170, 0);
            this.m_pal_bottom_sub2.Name = "m_pal_bottom_sub2";
            this.m_pal_bottom_sub2.Size = new System.Drawing.Size(173, 35);
            this.m_pal_bottom_sub2.TabIndex = 2;
            // 
            // m_txt_service_state
            // 
            this.m_txt_service_state.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left)));
            this.m_txt_service_state.AutoSize = true;
            this.m_txt_service_state.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_service_state.Location = new System.Drawing.Point(68, 9);
            this.m_txt_service_state.Name = "m_txt_service_state";
            this.m_txt_service_state.Size = new System.Drawing.Size(93, 19);
            this.m_txt_service_state.TabIndex = 5;
            this.m_txt_service_state.Text = "服务启动";
            this.m_txt_service_state.TextAlign = System.Drawing.ContentAlignment.TopCenter;
            // 
            // label8
            // 
            this.label8.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left)));
            this.label8.AutoSize = true;
            this.label8.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label8.Location = new System.Drawing.Point(7, 9);
            this.label8.Name = "label8";
            this.label8.Size = new System.Drawing.Size(62, 19);
            this.label8.TabIndex = 6;
            this.label8.Text = "网管:";
            this.label8.TextAlign = System.Drawing.ContentAlignment.TopCenter;
            // 
            // splitter2
            // 
            this.splitter2.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.splitter2.Location = new System.Drawing.Point(167, 0);
            this.splitter2.Name = "splitter2";
            this.splitter2.Size = new System.Drawing.Size(3, 35);
            this.splitter2.TabIndex = 1;
            this.splitter2.TabStop = false;
            // 
            // m_pal_bottom_sub1
            // 
            this.m_pal_bottom_sub1.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.m_pal_bottom_sub1.Controls.Add(this.m_txt_conn_state);
            this.m_pal_bottom_sub1.Controls.Add(this.label7);
            this.m_pal_bottom_sub1.Dock = System.Windows.Forms.DockStyle.Left;
            this.m_pal_bottom_sub1.Location = new System.Drawing.Point(0, 0);
            this.m_pal_bottom_sub1.Name = "m_pal_bottom_sub1";
            this.m_pal_bottom_sub1.Size = new System.Drawing.Size(167, 35);
            this.m_pal_bottom_sub1.TabIndex = 0;
            // 
            // m_txt_conn_state
            // 
            this.m_txt_conn_state.AutoSize = true;
            this.m_txt_conn_state.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_conn_state.Location = new System.Drawing.Point(68, 9);
            this.m_txt_conn_state.Name = "m_txt_conn_state";
            this.m_txt_conn_state.Size = new System.Drawing.Size(93, 19);
            this.m_txt_conn_state.TabIndex = 4;
            this.m_txt_conn_state.Text = "通讯断开";
            // 
            // label7
            // 
            this.label7.AutoSize = true;
            this.label7.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label7.Location = new System.Drawing.Point(5, 9);
            this.label7.Name = "label7";
            this.label7.Size = new System.Drawing.Size(62, 19);
            this.label7.TabIndex = 3;
            this.label7.Text = "机台:";
            this.label7.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // m_pal_order_log
            // 
            this.m_pal_order_log.BackColor = System.Drawing.SystemColors.ActiveBorder;
            this.m_pal_order_log.Controls.Add(this.m_rtb_log);
            this.m_pal_order_log.Controls.Add(this.label3);
            this.m_pal_order_log.Controls.Add(this.label2);
            this.m_pal_order_log.Controls.Add(this.m_txt_test_workOrder);
            this.m_pal_order_log.Controls.Add(this.m_txt_material_no);
            this.m_pal_order_log.Controls.Add(this.m_txt_order_no);
            this.m_pal_order_log.Controls.Add(this.label1);
            this.m_pal_order_log.Controls.Add(this.splitter1);
            this.m_pal_order_log.Dock = System.Windows.Forms.DockStyle.Top;
            this.m_pal_order_log.Location = new System.Drawing.Point(0, 0);
            this.m_pal_order_log.Name = "m_pal_order_log";
            this.m_pal_order_log.Size = new System.Drawing.Size(1274, 69);
            this.m_pal_order_log.TabIndex = 0;
            // 
            // m_rtb_log
            // 
            this.m_rtb_log.BackColor = System.Drawing.SystemColors.WindowText;
            this.m_rtb_log.Cursor = System.Windows.Forms.Cursors.Default;
            this.m_rtb_log.Dock = System.Windows.Forms.DockStyle.Fill;
            this.m_rtb_log.Font = new System.Drawing.Font("新宋体", 9F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_rtb_log.ForeColor = System.Drawing.SystemColors.MenuHighlight;
            this.m_rtb_log.Location = new System.Drawing.Point(345, 0);
            this.m_rtb_log.Name = "m_rtb_log";
            this.m_rtb_log.Size = new System.Drawing.Size(929, 69);
            this.m_rtb_log.TabIndex = 1;
            this.m_rtb_log.Text = "";
            this.m_rtb_log.TextChanged += new System.EventHandler(this.m_rtb_log_TextChanged);
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.BackColor = System.Drawing.Color.Black;
            this.label3.Font = new System.Drawing.Font("新宋体", 10.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label3.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(224)))), ((int)(((byte)(224)))), ((int)(((byte)(224)))));
            this.label3.Location = new System.Drawing.Point(3, 47);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(67, 14);
            this.label3.TabIndex = 2;
            this.label3.Text = "工单号：";
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.BackColor = System.Drawing.Color.Black;
            this.label2.Font = new System.Drawing.Font("新宋体", 10.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label2.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(224)))), ((int)(((byte)(224)))), ((int)(((byte)(224)))));
            this.label2.Location = new System.Drawing.Point(3, 27);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(82, 14);
            this.label2.TabIndex = 2;
            this.label2.Text = "物料编号：";
            // 
            // m_txt_test_workOrder
            // 
            this.m_txt_test_workOrder.AutoSize = true;
            this.m_txt_test_workOrder.BackColor = System.Drawing.Color.Black;
            this.m_txt_test_workOrder.Font = new System.Drawing.Font("新宋体", 10.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_txt_test_workOrder.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(224)))), ((int)(((byte)(224)))), ((int)(((byte)(224)))));
            this.m_txt_test_workOrder.Location = new System.Drawing.Point(104, 47);
            this.m_txt_test_workOrder.Name = "m_txt_test_workOrder";
            this.m_txt_test_workOrder.Size = new System.Drawing.Size(103, 14);
            this.m_txt_test_workOrder.TabIndex = 2;
            this.m_txt_test_workOrder.Text = "XXXXXXXXXXXX";
            // 
            // m_txt_material_no
            // 
            this.m_txt_material_no.AutoSize = true;
            this.m_txt_material_no.BackColor = System.Drawing.Color.Black;
            this.m_txt_material_no.Font = new System.Drawing.Font("Arial", 10.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.m_txt_material_no.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(224)))), ((int)(((byte)(224)))), ((int)(((byte)(224)))));
            this.m_txt_material_no.Location = new System.Drawing.Point(104, 27);
            this.m_txt_material_no.Name = "m_txt_material_no";
            this.m_txt_material_no.Size = new System.Drawing.Size(162, 16);
            this.m_txt_material_no.TabIndex = 2;
            this.m_txt_material_no.Text = "HG-LPDDR3-45876788-";
            this.m_txt_material_no.Click += new System.EventHandler(this.m_txt_material_no_Click);
            // 
            // m_txt_order_no
            // 
            this.m_txt_order_no.AutoSize = true;
            this.m_txt_order_no.BackColor = System.Drawing.Color.Black;
            this.m_txt_order_no.Font = new System.Drawing.Font("Arial", 10.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.m_txt_order_no.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(224)))), ((int)(((byte)(224)))), ((int)(((byte)(224)))));
            this.m_txt_order_no.Location = new System.Drawing.Point(104, 7);
            this.m_txt_order_no.Name = "m_txt_order_no";
            this.m_txt_order_no.Size = new System.Drawing.Size(178, 16);
            this.m_txt_order_no.TabIndex = 2;
            this.m_txt_order_no.Text = "ORD123456789ABCDEFG";
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.BackColor = System.Drawing.Color.Black;
            this.label1.Font = new System.Drawing.Font("新宋体", 10.5F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label1.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(224)))), ((int)(((byte)(224)))), ((int)(((byte)(224)))));
            this.label1.Location = new System.Drawing.Point(3, 5);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(82, 14);
            this.label1.TabIndex = 2;
            this.label1.Text = "订单编号：";
            // 
            // splitter1
            // 
            this.splitter1.BackColor = System.Drawing.SystemColors.ActiveCaptionText;
            this.splitter1.BorderStyle = System.Windows.Forms.BorderStyle.Fixed3D;
            this.splitter1.Location = new System.Drawing.Point(0, 0);
            this.splitter1.Name = "splitter1";
            this.splitter1.Size = new System.Drawing.Size(345, 69);
            this.splitter1.TabIndex = 0;
            this.splitter1.TabStop = false;
            // 
            // m_pal_center
            // 
            this.m_pal_center.BackColor = System.Drawing.SystemColors.ControlDark;
            this.m_pal_center.Controls.Add(this.m_pnl_statusList);
            this.m_pal_center.Controls.Add(this.m_pal_status_pal_bar);
            this.m_pal_center.Dock = System.Windows.Forms.DockStyle.Fill;
            this.m_pal_center.Location = new System.Drawing.Point(4, 106);
            this.m_pal_center.Margin = new System.Windows.Forms.Padding(2, 2, 2, 2);
            this.m_pal_center.Name = "m_pal_center";
            this.m_pal_center.Size = new System.Drawing.Size(1274, 456);
            this.m_pal_center.TabIndex = 4;
            // 
            // m_pnl_statusList
            // 
            this.m_pnl_statusList.AutoScroll = true;
            this.m_pnl_statusList.BackColor = System.Drawing.Color.Black;
            this.m_pnl_statusList.Dock = System.Windows.Forms.DockStyle.Fill;
            this.m_pnl_statusList.Location = new System.Drawing.Point(0, 0);
            this.m_pnl_statusList.Margin = new System.Windows.Forms.Padding(2, 0, 2, 2);
            this.m_pnl_statusList.Name = "m_pnl_statusList";
            this.m_pnl_statusList.Size = new System.Drawing.Size(1274, 452);
            this.m_pnl_statusList.TabIndex = 1;
            this.m_pnl_statusList.Paint += new System.Windows.Forms.PaintEventHandler(this.m_pnl_statusList_Paint);
            // 
            // m_pal_status_pal_bar
            // 
            this.m_pal_status_pal_bar.BackColor = System.Drawing.SystemColors.ButtonFace;
            this.m_pal_status_pal_bar.Dock = System.Windows.Forms.DockStyle.Bottom;
            this.m_pal_status_pal_bar.Location = new System.Drawing.Point(0, 452);
            this.m_pal_status_pal_bar.Margin = new System.Windows.Forms.Padding(2, 2, 2, 2);
            this.m_pal_status_pal_bar.Name = "m_pal_status_pal_bar";
            this.m_pal_status_pal_bar.Size = new System.Drawing.Size(1274, 4);
            this.m_pal_status_pal_bar.TabIndex = 0;
            // 
            // m_bgw_ui_update
            // 
            this.m_bgw_ui_update.DoWork += new System.ComponentModel.DoWorkEventHandler(this.m_bgw_ui_update_DoWork);
            // 
            // m_richbox_update_timer
            // 
            this.m_richbox_update_timer.Enabled = true;
            this.m_richbox_update_timer.Interval = 500;
            this.m_richbox_update_timer.Tick += new System.EventHandler(this.m_richbox_update_timer_Tick);
            // 
            // MainForm
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 12F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(1282, 722);
            this.ControlBox = false;
            this.Controls.Add(this.m_pal_center);
            this.Controls.Add(this.panel2);
            this.Controls.Add(this.panel1);
            this.DoubleBuffered = true;
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(2, 2, 2, 2);
            this.Name = "MainForm";
            this.Padding = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.WindowState = System.Windows.Forms.FormWindowState.Maximized;
            this.FormClosing += new System.Windows.Forms.FormClosingEventHandler(this.MainForm_FormClosing);
            this.Load += new System.EventHandler(this.MainForm_Load);
            this.panel1.ResumeLayout(false);
            this.panel1.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.pictureBox1)).EndInit();
            this.panel2.ResumeLayout(false);
            this.m_pal_bottom_tab.ResumeLayout(false);
            this.panel6.ResumeLayout(false);
            this.panel6.PerformLayout();
            this.panel5.ResumeLayout(false);
            this.panel5.PerformLayout();
            this.panel4.ResumeLayout(false);
            this.panel4.PerformLayout();
            this.panel3.ResumeLayout(false);
            this.panel3.PerformLayout();
            this.m_pal_bottom_sub2.ResumeLayout(false);
            this.m_pal_bottom_sub2.PerformLayout();
            this.m_pal_bottom_sub1.ResumeLayout(false);
            this.m_pal_bottom_sub1.PerformLayout();
            this.m_pal_order_log.ResumeLayout(false);
            this.m_pal_order_log.PerformLayout();
            this.m_pal_center.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.Panel panel1;
        private System.Windows.Forms.Panel panel2;
        private System.Windows.Forms.Panel m_pal_order_log;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Label m_txt_test_workOrder;
        private System.Windows.Forms.Label m_txt_material_no;
        private System.Windows.Forms.Label m_txt_order_no;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.RichTextBox m_rtb_log;
        private System.Windows.Forms.Splitter splitter1;
        private System.Windows.Forms.Panel m_pal_center;
        private System.Windows.Forms.Panel m_pnl_statusList;
        private System.Windows.Forms.Panel m_pal_status_pal_bar;
        private System.Windows.Forms.PictureBox pictureBox1;
        private System.Windows.Forms.Button m_bnt_title;
        private System.Windows.Forms.Panel m_pal_bottom_tab;
        private System.Windows.Forms.Button m_btn_pause;
        private System.Windows.Forms.Button m_btn_start;
        private System.Windows.Forms.Button m_btn_setting;
        private System.Windows.Forms.Button m_btn_exit;
        private System.Windows.Forms.Splitter splitter4;
        private System.Windows.Forms.Panel panel3;
        private System.Windows.Forms.Splitter splitter3;
        private System.Windows.Forms.Splitter splitter2;
        private System.Windows.Forms.Panel m_pal_bottom_sub1;
        private System.Windows.Forms.Label m_txt_online_team;
        private System.Windows.Forms.Label label9;
        private System.Windows.Forms.Panel m_pal_bottom_sub2;
        private System.Windows.Forms.Label m_txt_service_state;
        private System.Windows.Forms.Label label8;
        private System.Windows.Forms.Label m_txt_conn_state;
        private System.Windows.Forms.Label label7;
        private System.Windows.Forms.Label m_txt_work_time;
        private System.Windows.Forms.Label m_txt_work_mode;
        private System.Windows.Forms.Splitter splitter5;
        private System.Windows.Forms.Panel panel5;
        private System.Windows.Forms.Panel panel4;
        private System.Windows.Forms.Label m_txt_workStage;
        private System.Windows.Forms.Label label11;
        private System.ComponentModel.BackgroundWorker m_bgw_ui_update;
        private System.Windows.Forms.Panel panel6;
        private System.Windows.Forms.Label m_txt_emi_path;
        private System.Windows.Forms.Label label5;
        private System.Windows.Forms.Splitter splitter6;
        private System.Windows.Forms.Label m_txt_test_tatistics;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Timer m_richbox_update_timer;
    }
}