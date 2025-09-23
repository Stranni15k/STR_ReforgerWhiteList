class STR_WL_CB : RestCallback
{
	int m_PlayerId;

	void STR_WL_CB(int playerId)
	{
		m_PlayerId = playerId;
	}

	override void OnSuccess(string data, int dataSize)
	{
		bool whitelisted;
		SCR_JsonLoadContext ctx = new SCR_JsonLoadContext();
		ctx.ImportFromString(data);
		ctx.ReadValue("whitelisted", whitelisted);

		PlayerManager pm = GetGame().GetPlayerManager();
		string name = pm.GetPlayerName(m_PlayerId);

		if (whitelisted)
		{
			PrintFormat("[STR][WL] ACCEPT pid=%1 name=%2", m_PlayerId, name);
			return;
		}

		PrintFormat("[STR][WL] DENY pid=%1 name=%2", m_PlayerId, name);
		pm.KickPlayer(m_PlayerId, PlayerManagerKickReason.KICK, 0);
	}

	override void OnError(int errorCode)
	{
		PrintFormat("[STR][WL] HTTP error %1 for pid=%2", errorCode, m_PlayerId);
	}

	override void OnTimeout()
	{
		PrintFormat("[STR][WL] HTTP timeout for pid=%1", m_PlayerId);
	}
}

modded class SCR_BaseGameMode
{
	static string s_WLBase = "";
	ref array<ref STR_WL_CB> m_WL_CBs = {};

	override void OnGameStart()
	{
		super.OnGameStart();
		if (!Replication.IsServer()) return;

		SCR_JsonLoadContext cfg = new SCR_JsonLoadContext();
		string urlFromFile;
		if (cfg.LoadFromFile("$profile:WhitelistURL.json") && cfg.ReadValue("url", urlFromFile))
			s_WLBase = urlFromFile;

		PrintFormat("[STR][WL] base url=%1", s_WLBase);
		GetOnPlayerAuditSuccess().Insert(OnAuditWL);
	}

	void OnAuditWL(int iPlayerID)
	{
		PrintFormat("[STR][WL] OnAuditWL triggered, pid=%1", iPlayerID);

		if (s_WLBase == "")
		{
			Print("[STR][WL] SKIP: empty base url");
			return;
		}

		string uid = GetGame().GetBackendApi().GetPlayerIdentityId(iPlayerID);
		PrintFormat("[STR][WL] raw uid=%1", uid);

		uid.Trim();
		uid.ToLower();

		string url = string.Format("%1/%2", s_WLBase, uid);
		PrintFormat("[STR][WL] GET %1", url);

		RestContext ctx = GetGame().GetRestApi().GetContext(url);
		STR_WL_CB cb = new STR_WL_CB(iPlayerID);
		m_WL_CBs.Insert(cb);
		ctx.GET(cb, "");
	}
}