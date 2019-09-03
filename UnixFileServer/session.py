#!/usr/bin/python
# -*- coding: utf8 -*-
import os
import sys
import posix_ipc as pos #raccourci module
import signal
import readline

monPid = str(os.getpid())

fileVersServeur = 0
fileVersClient = 0
fileConfirmeSup = 0
fileReponseSup = 0

#Classe chargée de gérer les limites de temps
class Alarm(Exception):
    pass

# encapsulation de tout ce qui englobe la création de la file de message
def cree_file():
	global fileVersServeur
	global fileVersClient
	global fileReponseSup
	try:
		fileVersServeur = pos.MessageQueue("/fileVersServeur")
	except:
		print("File vers serveur non existant! veuillez lancer servfic")
		sys.exit(2)
		
	try:
		fileReponseSup = pos.MessageQueue("/reponseSup")
	except pos.ExistentialError:
		print("fileConfirmationSup pas existante(pas normal)")

    
def demander_consulter_enregistrement(idEnr):
	requete = "CONSULTATION:"+str(monPid)+":"+str(idEnr)
	fileVersServeur.send(requete)

	#Maintenant on attend la réponse sur une file crée grâce au pid du client
	try:
		fileVersClient = pos.MessageQueue("/fileVersClient"+str(monPid),pos.O_CREAT|pos.O_EXCL)

	except pos.ExistentialError:
		print("/fileVersClient{} déjà existante".format(monPid))
		fileVersClient = pos.MessageQueue("/fileVersClient"+str(monPid),pos.O_CREAT)

	reponse = fileVersClient.receive()[0]
	print (reponse)
	fileVersClient.unlink()

def	demander_visualiser():
	requete = "VISUALISER:"+str(monPid)
	fileVersServeur.send(requete)
	try:
		fileVersClient = pos.MessageQueue("/fileVersClient"+str(monPid),pos.O_CREAT|pos.O_EXCL)

	except pos.ExistentialError:
		print("/fileVersClient{} déjà existante".format(monPid))
		fileVersClient = pos.MessageQueue("/fileVersClient"+str(monPid),pos.O_CREAT)

	reponse = fileVersClient.receive()[0]
	print (reponse)
	fileVersClient.unlink()
	
def demander_adjoindre():
	print("Saisissez ici le texte de l'enregistrement à adjoindre")
	print("Faites Ctrl+D quand vous avez fini d'entrer votre entregistrement\n")
	# On met un input multiligne
	texte = sys.stdin.read()
	requete = "ADJOINDRE:"+str(monPid)+":"+str(texte)
	fileVersServeur.send(requete)
	print("\n---------------")
	print("Enregistrement envoyé")
	print("---------------")
	
def demander_supprimer(idEnr):
	requete = "SUPPRIMER:"+str(monPid)+":"+str(idEnr)
	fileVersServeur.send(requete, priority=1) #Priorité plus elevée car c'est une suppression
	print("Demande de suppression envoyée...")
	
	#On attend la demande de confirmation qui vient par une file
	fileConfirmeSup = pos.MessageQueue("/confirmeSup")
	#Si on renvoie le délai, c'est que le fichier existe et qu'on peut le supprimer. Sinon c'est impossible d'ouvrir le fichier (ex: introuvable)
	reponse = fileConfirmeSup.receive()[0] #Le serveur répond qunad il traite la demande en envoyant le délai.
	
	if (reponse == "ENREGISTREMENT INTROUVABLE"):
		print("Cet enregistrement n'existe pas/plus sur le serveur.")
	else:
		delai = int(reponse)
		#Tant qu'on a pas la réponse on attend...
		
		print("Vous avez demandé à supprimer l'enregistrement {}. \nConfirmez vous? (O/N)\nVous avez {} secondes pour répondre".format(idEnr,delai))
		signal.alarm(delai)  #Temps pour répondre...
		try:
			confirmation = raw_input("> ")
			#Si réponse à temps: On ouvre la file et on envoie la réponse au serveur. Si pas réponse à temps on quitte la fonction. et les files ne sont pas crées
			try:
				fileReponseSup = pos.MessageQueue("/reponseSup")
			except pos.ExistentialError:
				print("fileReponseSup existante et ce n'est pas à moi de la crée")
				fileReponseSup = pos.MessageQueue("/reponseSup"+str(monPid),pos.O_CREAT)
			fileReponseSup.send(str(confirmation))
			signal.alarm(0) #Reset du timer
		except Alarm:
			print("Temps écoulé.")
'''
Fonction permettant d'avoir une entrée interactive
Met un input avec du texte déjà prérempli (paramètre défaut)
Le paramètre prompt est équivalent au paramètre d'un input normal
Le texte prérempli devient alors éditable

'''
def input_interactif(prompt, defaut):
    readline.set_startup_hook(lambda: readline.insert_text(defaut[:-1]))
    try:
        return raw_input(prompt)+"\n"
    finally:
        readline.set_startup_hook()

def demander_modifier(idEnr):
    '''
	Etapes pour procéder à une modification :
	1 lecture
	2 affichage
	3 edit interactif
	4 écriture coté serveur
	'''

    #Demande de lecture spéciale pour contenir le délai
    requete = "MODIFLEC:" + str(monPid) + ":" + str(idEnr)
    fileVersServeur.send(requete, priority=1) #Priorité plus elevée car c'est une modification
    print("Demande de lecture envoyée...")
    # Maintenant on attend la réponse sur une file crée grâce au pid du client
    try:
        fileVersClient = pos.MessageQueue("/fileVersClient" + str(monPid), pos.O_CREAT | pos.O_EXCL)

    except pos.ExistentialError:
        print("/fileVersClient{} déjà existante".format(monPid))
        fileVersClient = pos.MessageQueue("/fileVersClient" + str(monPid), pos.O_CREAT)

    reponse = fileVersClient.receive()[0]
    if (reponse == "ENREGISTREMENT INTROUVABLE"):
        print("Cet enregistrement n'existe pas/plus sur le serveur.")
    else:
        #Notre réponse serveur est sous cette forme :
        #delai:Enregistrement ==> On découpe le string en deux parties
        reponse = reponse.split(":")
        delai = int(reponse[0])
        #On joint le texte à partir de la case 1 au cas où l'enregistrement contient des double points
        #Il ne s'agit que d'une précaution pour ne pas juste utiliser reponse[1]
        texte = ''.join(reponse[1:])
        signal.alarm(delai)
        try:
            #on modifie interactivement le texte
            envoi = input_interactif("Procédez à la modification dans les {} secondes: \n".format(delai),texte)
            requete = "MODIFIER:" + str(monPid) + ":" + str(idEnr) + ":" + envoi
            print("Demande de modification envoyée...")
            fileVersServeur.send(requete, priority=1)  # Priorité plus elevée car c'est une modification
        except Alarm:
            print("\nTemps écoulé.\n")
        signal.alarm(0)
    fileVersClient.unlink()
	
#Fonction appelée quand l'utilisateur ne répond pas à temps à une supp / modification
def handler_hors_delai(signum, frame):
    raise Alarm
	
#fonction menu:
#Affiche les options possibles sous la forme d'un... menu.
def menu():
	print ("Veuillez taper le numéro de l'action que vous souhaitez effectuer.")
	print ("1 - Consulter un enregistrement")
	print ("2 - Visualiser tout le fichier")
	print ("3 - Adjoindre un enregistrement")
	print ("4 - Supprimer un enregistrement")
	print ("5 - Modifier un enregistrement")
	print ("0 - Quitter :-( ")

	choix = int(raw_input("> "))
	if (choix == 1):
		print ("Indiquez l'id de l'enregistrement à consulter")
		idEnr = raw_input("> ")
		demander_consulter_enregistrement(idEnr)
	elif (choix == 2):
		demander_visualiser()
	elif (choix == 3):
		demander_adjoindre()
	elif (choix == 4):
		print ("Indiquez l'id de l'enregistrement à supprimer")
		idEnr = raw_input("> ")
		demander_supprimer(idEnr)
	elif (choix == 5):
		print ("Indiquez l'id de l'enregistrement à modifier")
		idEnr = raw_input("> ")
		demander_modifier(idEnr)
	elif (choix == 0):
		print("Fin des requêtes, fermeture de la session!")
		sys.exit(2)
	else:
		print (" Merci de répondre avec un chiffre entre 0 et 5")

def main(argv):
	#pos.MessageQueue("/reponseSup").unlink()
	signal.signal(signal.SIGALRM, handler_hors_delai)
	cree_file()
	print ("Bonjour et bienvenue sur MiageSession, votre PID est {}". format(monPid))
	while True:
		menu()
		
if __name__ == "__main__":
	main(sys.argv[1:])
