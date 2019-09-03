#!/usr/bin/python
# -*- coding: utf8 -*-
import os
import sys
import time
import re
import getopt
import threading
import signal
import posix_ipc as pos #raccourci module


enregistrements = {} # Association clef/valeur, ou les clefs sont les id des enregistrements et les valeurs les textes des enregistrements
fichierCible = "" # Le fichier d'enregistrement (peut être vide ou composé d'enregistrement valides)
delai = 9999 # Le délai avant le timeOut. -1 de base, sinon il est modifié par -d.
fileVersServeur = 0 # L'outil IPC qui va nous permettre de papoter entre session(s).py et servfic
idSequence = -1
fileConfirmeSup = 0
fileReponseSup = 0
threadAdjonction = 1

filsEnCours =0
threadEnCours =[]
	

#Fonction flag_check:
#Appelée au lancement du programme pour vérifier les petits drapeaux -d et -f (et que les para soient valides)
def flag_check(argv):
    #On précise "global" car on modifie ces variables
    global delai
    global fichierCible

    #try/except au cas ou y'a des erreurs de parse
    try:
        opts, args = getopt.getopt(argv, "f:d:", ["fichier=", "delai="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    #boucle pour passer sur les drapeaux
    for opt, arg in opts:
        if opt in ("-f", "--fichier"):
            fichierCible = arg
        elif opt in ("-d", "--delai"):
            try:
                int(arg)
                delai = arg

            except:
                print("Le paramètre -d doit être un entier.")
                sys.exit(2)

#Signal pour gérer la fermeture du programme
#Au lieu de quitter d'un coup on écrase le fichier courant par ce qu'il y a dans la variable enregistrement
def fermer_programme(signal, frame):
    #appelée quand vient l'heure de fermer notre programme avec ^C
    fileVersServeur.unlink()
    fileReponseSup.unlink()
    fileConfirmeSup.unlink()
    fich = open(fichierCible, "r")
    wr = open(fichierCible, "w")

    for cle,val in enregistrements.items():
        wr.write('--enregistrement_{}_--\n{}'.format(cle,val))

#Fonction verif_ficher:
#Pour être un fichier d'enregistrement valide, soit le fichier est complètement vide,
#soit il n'y a que des enregistrements valides dedans
def verif_fichier():
    #try/except d'ouverture de fichier
    try:
        fich = open(fichierCible, "r")
    except IOError:
        print("Impossible de trouver {}".format(fichierCible))
        sys.exit(2)

    #On vérifie si le fichier n'est a qqch d'écrit dedans. Si oui, on le parse
    if os.path.getsize(fichierCible) > 0:
        statutParse = parse_initial()
        if len(enregistrements) == 0: #après l'appel à parse_initial sur un fichier non vide, il faut au moins 1 enregistrement, sinon fichier invalide
            print("Le fichier spécifié ne contient pas d'enregistrement valide")
            sys.exit(2)

#Fonction parse_initial()
#On parcours le fichier cible. La lecture de la première ligne est manuelle (voir var premiereLigne) sinon c'est casse-pied à parse
#Ensuite on boucle. Pour chaque ligne:
# a) C'est une ligne "header" (ex: --enregistrement_2_--) et délimite le début de l'enregistrement
# 	Dans ce cas on enregistre dans notre association clef/valeur l'id qu'on avait en mémoire en clef, et tout le texte qu'on a vu plus en amont en valeur (soit la variable ligneTxt)
#	Ensuite, on remplace l'id qu'on a en mémoire par celui qu'on vient de lire (dans notre exemple: 2)
# b) sinon, c'est une ligne d'enregistrement: on l'ajoute à la vairable ligneTxt
# qui n'est pas de l'enregistrement (donc pas sous la forme --enregistrement_n_--)

#TO POTENTIELLEMENT DO CAR NOT SUPER IMPORTANT: vérifier dans le fichier parse qu'on a pas de doublon sur la clef d'un enregistrement (ex: pas deux fois un enregistrement_2_)
def parse_initial():
    global idSequence
    fich = open(fichierCible, "r")
    ligneTxt = ""
    idTmp = -1

    premiereLigne = fich.readline()
    m = re.search("\-\-enregistrement\_(?P<id_enreg>\d+)\_\-\-", premiereLigne) #regex qui permet de savoir si c'est un enregistrement
    if m is not None:
        idTmp = int(m.group('id_enreg')) #notre groupe de capture id_enreg permet de stocker la var
    else:
        print("Première ligne non valide") #si la première ligne est pas un header c'est une erreur
        sys.exit(2)

    for line in fich:
        #verif regex...
        m = re.search("\-\-enregistrement\_(?P<id_enreg>\d+)\_\-\-", line)
        if m is not None: #J'ai match un header
            enregistrements[idTmp] = ligneTxt #Stockage dans l'association clef valeur de l'id temporaire et de tout le texte que j'ai pu voir
            idTmp = int(m.group('id_enreg'))
            ligneTxt = "" # On remet la ligne de texte à 0 pour les prochains enregistrements...
        else: #C'est une ligne de texte
            ligneTxt = ligneTxt + line
    else: #Fin du fichier: j'oublie pas de stocker le dernier enregistrement
        enregistrements[idTmp] = ligneTxt
    #Finalement on regarde quel est l'id le plus élevé (ce qui nous servira pour les futures adjonctions)
    idSequence = max(enregistrements.keys()) +1

# fonction appelée quand l'utilisateur tape n'importe quoi pour ouvrir servfic
def usage():
    print ("Usage de servfic: servfic -f <nom_de_fichier> [ -d <nombre_de_secondes> ]")

# encapsulation de tout ce qui englobe la création de la file de message
def cree_file():
    global fileVersServeur
    global fileReponseSup
    global fileConfirmeSup

    try:
        fileVersServeur = pos.MessageQueue("/fileVersServeur",pos.O_CREAT|pos.O_EXCL)

    except pos.ExistentialError:
        print("File vers serveur déjà existante")
        fileVersServeur = pos.MessageQueue("/fileVersServeur",pos.O_CREAT)

    #Creation de la file de message servant à confirmer la suppression
    try:
        fileReponseSup = pos.MessageQueue("/reponseSup",pos.O_CREAT|pos.O_EXCL,max_messages = 1)

    except pos.ExistentialError:
        print("fileConfirmationSup déjà existante(ce ne devrait pas être le cas)")
        fileReponseSup = pos.MessageQueue("/reponseSup",pos.O_CREAT,max_messages = 1)

    try:
        fileConfirmeSup = pos.MessageQueue("/confirmeSup",pos.O_CREAT|pos.O_EXCL,max_messages = 1)

    except pos.ExistentialError:
        print("File supconfirm déjà existant ...")
        fileConfirmeSup = pos.MessageQueue("/confirmeSup",pos.O_CREAT)

#Fonction qui bloque le serveur tant que tous les threads n'ont pas fait leur travail
def attendreToutLeMonde():
	print ("Je dois vérifier que les {} threads ont bien fini avant de continuer.".format(len(threadEnCours)))
	global threadEnCours	
	for t in threadEnCours:
		t.join()
	threadEnCours = []
#fonction main:
#Vérifie les drapeaux, parse le fichier passé en parmètre, initialise la file de message
#puis boucle à l'infini pour attendre des messages
def main(argv):
    print ("Pour terminer le serveur, faites Ctrl+C. Le fichier cible sera alors modifié selon les dernières modificaitons...")
    global threadAdjonction
    global threadEnCours
    global filsEnCours
    
    flag_check(argv)
    verif_fichier()
    cree_file()
    signal.signal(signal.SIGINT, fermer_programme)
    while True:
        try:
            message = fileVersServeur.receive()
        except pos.SignalError:
            print("Le programme a été interrompu par l'utilisateur...")
            sys.exit(2)
        #Tous les messages que l'on reçoit par les clients sont sous la forme suivante
        #OPERATION:PID:ARGUMENTSUP
        #Pour consulter enregistrement, l'argument sup = l'id de l'enregistrement à consulter
        #Pour consulter tout, il n'y a pas d'argument sup... etc
        requete = message[0].split(":")
        objetRequete = requete[0]
        pidClient = requete[1]


        if (objetRequete == "CONSULTATION"):
		t = threading.Thread(target=consulter_enregistrement, args=(requete[2],pidClient,))
		threadEnCours.append(t)
		t.start()
        elif (objetRequete == "VISUALISER"):
		t = threading.Thread(target=visualiser, args=(pidClient,))
		threadEnCours.append(t)
		t.start()
        elif (objetRequete == "ADJOINDRE"):
		t = threading.Thread(target=adjoindre_enregistrement, args=(requete[2],pidClient,))
		threadEnCours.append(t)
		t.start()
        elif (objetRequete == "SUPPRIMER"):
		attendreToutLeMonde()
		supprimer_enregistrement(requete[2],pidClient)
	elif (objetRequete == "MODIFIER"):
		attendreToutLeMonde()
		modifier_enregistrement(requete[2],''.join(requete[3:]),pidClient)
        #lecture spéciale permettant d'aussi envoyer le delai
	elif (objetRequete == "MODIFLEC"):
		attendreToutLeMonde()
	        consulter_enregistrement_delai(requete[2], pidClient)
        else:
            print('Requête inconnue')

#On regarde 1 seul enregistrement
def consulter_enregistrement(idEnr, pidClient):
    #on accède simplement à l'entrée du tableau global
    time.sleep(5)
    print("Je vais chercher l'enregistrement "+idEnr+" pour le client "+pidClient)
    if(enregistrements.get(int(idEnr)) != None):
        reponse = "Enregistrement "+str(idEnr)+" : "+str(enregistrements.get(int(idEnr)))
    else:
        #S'il n'en existe pas, on retourne un message d'erreur et on aide l'utilisateur en lui montrant
        #l'id le plus grand (au cas où il entre 100 quand il y en a 20)
        reponse = "Enregistrement non existant (plus grand = {})".format(idSequence-1)
    #On accède (sans créer si elle n'existe pas) la file générée par la session
    try:
        queueReponse = pos.MessageQueue("/fileVersClient"+str(pidClient))
        print("La queue pour ce client existe déjà (normal)")
    except pos.ExistentialError:
        print("La queue pour ce client n'existe pas et ce n'est pas normal")
        return
    queueReponse.send(reponse)
    threadEnCours.remove(threading.currentThread())

#consultation d'enregistrement spécifique à la modification car nécessite le délai
def consulter_enregistrement_delai(idEnr, pidClient):
    #on accède simplement à l'entrée du tableau global
    print("--------- Début opération de modification ---------")
    print("Je vais chercher l'enregistrement "+idEnr+" pour le client "+pidClient)
    if(enregistrements.get(int(idEnr)) != None):
        reponse = str(delai)+":"+str(enregistrements.get(int(idEnr)))
    else:
        reponse = "ENREGISTREMENT INTROUVABLE"
    try:
        queueReponse = pos.MessageQueue("/fileVersClient"+str(pidClient))
    except pos.ExistentialError:
        print("La queue pour ce client n'existe pas et ce n'est pas normal")
        return
    queueReponse.send(reponse)


#On consulte tout le fichier
def visualiser(pidClient):
    time.sleep(5)
    print("Je vais afficher tous les enregistrements pour le client "+pidClient)
    reponse = ""
    for cle,val in enregistrements.items():
        reponse =reponse + 'N°'+str(cle)+' : '+str(val)

    try:
        queueReponse = pos.MessageQueue("/fileVersClient"+str(pidClient))
    except pos.ExistentialError:
        print("La queue pour ce client n'existe pas et ce n'est pas normal")
        return
    queueReponse.send(reponse)
    threadEnCours.remove(threading.currentThread())

#On rajoute un enregistrement au document
def adjoindre_enregistrement(texte,pidClient):
    global idSequence
    time.sleep(5)
    print('---------------------')
    print('Adjonction de {} en position {}...'.format(texte,idSequence))
    print('---------------------')
    enregistrements[idSequence]=texte+"\n"
    idSequence = idSequence + 1
    print('---------------------')
    print('Enregistrement adjoint.')
    print('---------------------')
    threadEnCours.remove(threading.currentThread())

#NECESSITE QU'AUCUNE REQUETE NE SOIT EN COURS
def supprimer_enregistrement(idEnr,pidClient):
    print("Je vais peut être supprimer l'enregistrement "+idEnr+"pour le client "+pidClient)
    fileConfirmeSup = pos.MessageQueue("/confirmeSup")
    if(enregistrements.get(int(idEnr)) != None):
        fileConfirmeSup.send(str(delai))
        try:
            message = fileReponseSup.receive(int(delai)) #Dans un délai imparti fixé par l'utilisateur
            confirmationClient = message[0]
            if (confirmationClient == "O" or confirmationClient == "o"):
                del enregistrements[int(idEnr)]
                print("Suppression effectuée.")
            else: #On ne supprime pas
                print("Annulation de la demande de suppression...")
        except pos.BusyError:
            print("La réponse n'a pas été envoyée à temps...")

    else:
        #S'il n'en existe pas, on retourne un message d'erreur et on aide l'utilisateur en lui montrant
        #l'id le plus grand (au cas où il entre 100 quand il y en a 20)
        reponse = "ENREGISTREMENT INTROUVABLE"
        fileConfirmeSup.send(reponse)

#NECESSITE QU'AUCUNE REQUETE NE SOIT EN COURS
def modifier_enregistrement(idEnr,texte,pidClient):
    print('---------------------')
    print('Modification de l\'enregistrement {}...'.format(idEnr))
    print('---------------------')
    enregistrements[int(idEnr)] = texte
    print('---------------------')
    print('Enregistrement modifié.')
    print('---------------------')

if __name__ == "__main__":
    main(sys.argv[1:])
chosson
