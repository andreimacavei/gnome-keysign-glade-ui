
_data = {
    'key1' : {'id':'2048R/ED8312A2 2014-04-08',
              'fpr':'BEFDD433DCF8956D0D36011B4B032D3DED8312A2',
              'uids':[
                    {'uid':'John Doe john.doe@test.com',
                     'sigs':['ED8312A2', '6FB8DCCE']
                    },
                    {'uid':'John Foo (Test Key) john.foe@test.com',
                     'sigs':['ED8312A2']
                    }
                    ],
              'expiry':'2016-12-12',
              'nsigs':3
             },
    'key2' : {'id':'2048R/D32DFCFB 2015-08-20',
              'fpr':'B870D356F7ECD46CF2CEDF933BF372D3D32DFCFB',
              'uids':[
                    {'uid':'Foo Bar foo.bar@test.com',
                     'sigs':['D32DFCFB','6FB8DCCE']
                    }
                    ],
              'expiry':'2016-05-20',
              'nsigs':2
             },
    'key3' : {'id':'2048R/ED8312A2 2010-04-08',
              'fpr':'6011B4B032D3DED8312A2BEFDD433DCF8956D0D3',
              'uids':[
                    {'uid':'John Who john.who@test.com',
                     'sigs':['ED8312A2']
                    }
                    ],
              'expiry':'2016-07-14',
              'nsigs':1
             },
    'key4' : {'id':'2048R/D32DFCFB 2013-01-01',
              'fpr':'CEDF933BF372D3D32DFCFBB870D356F7ECD46CF2',
              'uids':[
                    {'uid':'Educated Foo edu.foo@test.com',
                     'sigs':['D32DFCFB','6FB8DCCE', '8956D0D3']
                    }
                    ],
              'expiry':'2020-05-05',
              'nsigs':3
             },
}

def get_secret_keys(pattern=None):
    data = None
    try:
        import keysign.gpgmh as gpgmh
    except ImportError as e:
        print e
        try:
            import gpgmh
        except ImportError as e:
            print e
            data = _data

    if data is None:
        keys = gpgmh.get_usable_secret_keys_dict()

        data = { k['fpr']: k   for k in keys['keys']}

    return _data


def format_listbox_keydata(keydata):
    keyid = keydata['id']
    uids = keydata['uids']
    expire = keydata['expiry']
    nsigs = keydata['nsigs']

    result = "<b>{0}</b>\t\t\t{1}\n".format(keyid, nsigs)
    for uid in uids:
        result += "{}\n".format(uid['uid'])
    result += "\n"
    result += "<small>Expires {}</small>".format(expire)

    return result

def format_details_keydata(keydata):
    result = ""
    for uid in keydata['uids']:
        result += "{}\n".format(uid['uid'])

    return result

def clean_fingerprint(fpr):
    res_fpr = ''.join(fpr.split())
    return res_fpr.upper()

def is_valid_fingerprint(fpr):
    cleaned_fpr = clean_fingerprint(fpr)
    if len(cleaned_fpr) != 40:
        return False

    return True


def format_fpr(fpr):
    res_fpr = ""
    for i in range(0, len(fpr), 4):
        res_fpr += fpr[i:i+4]
        if i != 0 and (i+4) % 20 == 0:
            res_fpr += "\n"
        else:
            res_fpr += " "
    res_fpr = res_fpr.rstrip()
    return res_fpr
