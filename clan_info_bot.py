import requests
import json
import asyncio
import aiohttp
import ssl
from datetime import datetime
import time

# Configurazione delle API
API_CONFIG = {
    'GUILD_INFO': 'https://free-ff-api-src-5plp.onrender.com/api/v1/guild/info/{guildId}',
    'PLAYER_INFO': 'https://ffinfo-mu.vercel.app/player-info?uid={uid}&region={region}',
    'BANNER': 'https://gmg-avatar-banner.vercel.app/Gmg-avatar-banner?uid={uid}&region={region}&key=IDK',
    'OUTFIT': 'https://ffoutfitapis.vercel.app/outfit-image?uid={uid}&region={region}&key=99day'
}

# Informazioni del clan NPT
CLAN_CONFIG = {
    'CLAN_ID': '3082766228',
    'REGION': 'ME',  # Cambiato da MENA a ME come richiesto
    'MEMBER_UIDS': [
        "1982843750", "2147717005", "8984654463", "6777807406", "380140258", 
        "5302948665", "6865125590", "655037876", "709223604", "1700466375", 
        "2297978144", "2443253758", "2760169702", "3078904109", "7765993064", 
        "7964907757", "8399040320", "8574920849", "8724073631", "8825536103", 
        "8905610409", "10983186579", "12269194707", "12584246958", "12795880783", 
        "12878399612"
    ]
}

class ClanInfoBot:
    def __init__(self):
        self.clan_id = CLAN_CONFIG['CLAN_ID']
        self.region = CLAN_CONFIG['REGION']
        self.member_uids = CLAN_CONFIG['MEMBER_UIDS']
        self.session = None
        self.failed_requests = 0
        self.max_retries = 3
        
    async def __aenter__(self):
        # Configura timeout e opzioni per una migliore gestione delle connessioni
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def get_clan_info(self):
        """Ottieni informazioni generali del clan"""
        # Estrai le informazioni del clan dal primo membro disponibile
        for uid in self.member_uids:
            player_info = await self.get_player_info(uid)
            if player_info and isinstance(player_info, dict):
                # Controlla se ci sono informazioni del clan nei dati del giocatore
                guild_info = player_info.get('GuildInfo', {})
                if guild_info and guild_info.get('clanId') == self.clan_id:
                    return guild_info
                    
                # Controlla anche nel formato alternativo
                player_data = player_info.get('player_info', {})
                clan_info = player_data.get('clanBasicInfo', {})
                if clan_info and clan_info.get('clanId') == self.clan_id:
                    return clan_info
        
        return None
            
    async def get_player_info(self, uid):
        """Ottieni informazioni di un singolo giocatore"""
        if not self.session:
            print("Session not initialized")
            return None
            
        retries = 0
        while retries < self.max_retries:
            try:
                url = API_CONFIG['PLAYER_INFO'].format(uid=uid, region=self.region)
                print(f"Fetching player info for UID {uid}")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.failed_requests = 0  # Reset contatore errori
                        return data
                    elif response.status == 404:
                        print(f"Player {uid} not found: {response.status}")
                        return None
                    elif response.status >= 500:
                        print(f"Server error fetching player info for {uid}: {response.status}")
                        retries += 1
                        if retries < self.max_retries:
                            await asyncio.sleep(2 ** retries)  # Backoff esponenziale
                        continue
                    else:
                        print(f"Error fetching player info for {uid}: {response.status}")
                        return None
            except asyncio.TimeoutError:
                print(f"Timeout fetching player info for {uid}, retry {retries + 1}/{self.max_retries}")
                retries += 1
                if retries < self.max_retries:
                    await asyncio.sleep(2 ** retries)
            except Exception as e:
                print(f"Exception in get_player_info for {uid}: {e}")
                retries += 1
                if retries < self.max_retries:
                    await asyncio.sleep(2 ** retries)
        return None
            
    async def get_member_details(self, uid):
        """Ottieni dettagli completi di un membro"""
        try:
            player_info = await self.get_player_info(uid)
            if not player_info:
                # Nessun fallback - restituisci None se non riusciamo a ottenere informazioni
                return None
                
            # Estrai le informazioni necessarie
            account_info = player_info.get('AccountInfo', player_info.get('player_info', {}))
            if 'basicInfo' in account_info:
                account_info = account_info['basicInfo']
            elif 'player_info' in player_info and 'basicInfo' in player_info['player_info']:
                account_info = player_info['player_info']['basicInfo']
                
            # Gestisci il caso in cui lastLoginAt potrebbe essere una stringa
            last_login = account_info.get('lastLoginAt', 0)
            if isinstance(last_login, str):
                try:
                    last_login = int(last_login)
                except ValueError:
                    last_login = 0
            elif isinstance(last_login, float):
                last_login = int(last_login)
                    
            current_time = int(time.time())
            
            member_data = {
                'uid': uid,
                'nickname': account_info.get('nickname', ''),
                'level': account_info.get('level', 0),
                'status': 'online' if last_login > (current_time - 3600) else 'offline',
                'region': account_info.get('region', self.region),
                'banner_url': API_CONFIG['BANNER'].format(uid=uid, region=self.region),
                'outfit_url': API_CONFIG['OUTFIT'].format(uid=uid, region=self.region),
                'glory': account_info.get('glory', account_info.get('honorScore', 0)),
                'realName': account_info.get('realName', '')
            }
            
            return member_data
        except Exception as e:
            print(f"Exception in get_member_details for {uid}: {e}")
            # Nessun fallback - restituisci None in caso di errore
            return None
            
    async def get_all_members_info(self):
        """Ottieni informazioni di tutti i membri del clan"""
        members_data = []
        print(f"Fetching info for {len(self.member_uids)} clan members...")
        
        # Processa i membri in batch più piccoli per evitare sovraccarico
        batch_size = 3
        for i in range(0, len(self.member_uids), batch_size):
            batch = self.member_uids[i:i+batch_size]
            tasks = [self.get_member_details(uid) for uid in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"Exception in batch processing: {result}")
                    continue
                if result:
                    members_data.append(result)
                    
            # Pausa più lunga tra i batch per ridurre il carico sulle API
            await asyncio.sleep(1)
            
        return members_data
        
    async def get_clan_summary(self):
        """Ottieni un riepilogo completo del clan"""
        try:
            # Ottieni informazioni del clan
            clan_info = await self.get_clan_info()
            
            # Ottieni informazioni dei membri
            members_info = await self.get_all_members_info()
            
            # Calcola statistiche
            total_members = len(members_info)
            online_members = len([m for m in members_info if m and m['status'] == 'online'])
            
            # Calcola livello medio
            total_level = sum(m['level'] for m in members_info if m and m['level'] > 0)
            avg_level = total_level // total_members if total_members > 0 else 0
            
            # Trova il membro con il livello più alto
            valid_members = [m for m in members_info if m and m['level'] > 0]
            highest_level_member = max(valid_members, key=lambda x: x['level']) if valid_members else None
            
            # Calcola gloria totale se disponibile
            total_glory = sum(m['glory'] for m in members_info if m and m['glory'] > 0)
            
            # Nome del clan (senza fallback)
            clan_name = ""
            if clan_info and isinstance(clan_info, dict):
                clan_name = clan_info.get('clanName', clan_info.get('name', ''))
            
            summary = {
                'clan_info': {
                    'id': self.clan_id,
                    'name': clan_name,
                    'region': self.region,
                    'total_glory': total_glory
                },
                'member_stats': {
                    'total_members': total_members,
                    'online_members': online_members,
                    'offline_members': total_members - online_members,
                    'average_level': avg_level,
                    'highest_level_member': {
                        'nickname': highest_level_member['nickname'] if highest_level_member else '',
                        'level': highest_level_member['level'] if highest_level_member else 0
                    } if highest_level_member else None
                },
                'members': [m for m in members_info if m],  # Filtra i membri None
                'timestamp': datetime.now().isoformat()
            }
            
            return summary
        except Exception as e:
            print(f"Exception in get_clan_summary: {e}")
            return None
            
    def print_clan_summary(self, summary):
        """Stampa un riepilogo leggibile del clan"""
        if not summary:
            print("Impossibile ottenere le informazioni del clan")
            return
            
        clan_info = summary['clan_info']
        member_stats = summary['member_stats']
        
        print("\n" + "="*60)
        print("           INFORMAZIONI CLAN NPT ESPORTS")
        print("="*60)
        print(f"Nome Clan: '{clan_info['name']}'")
        print(f"ID Clan: {clan_info['id']}")
        print(f"Regione: {clan_info['region']}")
        print(f"Gloria Totale: {clan_info['total_glory']}")
        print("-"*60)
        print(f"Membri Totali: {member_stats['total_members']}")
        print(f"Membri Online: {member_stats['online_members']}")
        print(f"Membri Offline: {member_stats['offline_members']}")
        print(f"Livello Medio: {member_stats['average_level']}")
        if member_stats['highest_level_member']:
            print(f"Membro con Livello Più Alto: {member_stats['highest_level_member']['nickname']} (Lv. {member_stats['highest_level_member']['level']})")
        print("="*60)
        
        print("\nDETTAGLI MEMBRI:")
        print("-"*100)
        print(f"{'Nickname':<15} {'UID':<12} {'Livello':<8} {'Stato':<10} {'Gloria':<8} {'Nome Reale':<15}")
        print("-"*100)
        
        for member in summary['members']:
            real_name = member.get('realName', '')
            # Mostra il nome reale solo se diverso dal nickname
            display_name = real_name if real_name != '' and real_name != member['nickname'] else ''
            print(f"{member['nickname']:<15} {member['uid']:<12} {member['level']:<8} {member['status']:<10} {member['glory']:<8} {display_name:<15}")
            
        print("-"*100)
        print(f"Ultimo Aggiornamento: {summary['timestamp']}")
        
    async def run_info_cycle(self):
        """Esegui un ciclo continuo di raccolta informazioni"""
        print("Avvio del Clan Info Bot...")
        print("Premi Ctrl+C per interrompere")
        
        try:
            while True:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Aggiornamento informazioni clan...")
                summary = await self.get_clan_summary()
                self.print_clan_summary(summary)
                
                # Attendi 5 minuti prima del prossimo aggiornamento
                print("\nProssimo aggiornamento tra 5 minuti...")
                await asyncio.sleep(300)  # 300 secondi = 5 minuti
                
        except KeyboardInterrupt:
            print("\nBot interrotto dall'utente")
        except Exception as e:
            print(f"Errore nel ciclo principale: {e}")

async def main():
    """Funzione principale"""
    async with ClanInfoBot() as bot:
        # Esegui un singolo aggiornamento
        print("Esecuzione di un singolo aggiornamento...")
        summary = await bot.get_clan_summary()
        bot.print_clan_summary(summary)
        
        # Se vuoi eseguire aggiornamenti continui, decommenta la linea seguente:
        # await bot.run_info_cycle()

if __name__ == "__main__":
    asyncio.run(main())